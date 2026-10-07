"""Account lockout, opaque sessions and one-use password links."""

import hmac
from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db.base import utcnow
from app.db.organization import (
    designations,
    employees,
    login_failures,
    password_tokens,
    sessions,
    user_accounts,
)
from app.errors import ApiError
from app.policies import Actor, require
from app.repositories import identity
from app.repositories import permissions as permission_rows
from app.security import (
    DUMMY_PASSWORD_HASH,
    MAX_PASSWORD_LENGTH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.services import login_email
from app.services.privileged_access import (
    PRIVILEGED_ACCOUNT_ROLES,
    lock_account_employee,
    lock_employee,
    require_owner_for_privileged_account,
)

LOCK_DURATION = timedelta(minutes=15)


def lock_active(locked_at, now) -> bool:
    return locked_at is not None and now < locked_at + LOCK_DURATION


def _valid_account_scope(
    designation: str, branch_id: UUID | None, department_id: UUID | None
) -> bool:
    if designation == "Owner":
        return branch_id is None and department_id is None
    return branch_id is not None and department_id is not None


async def login(session: AsyncSession, email: str, password: str) -> tuple[str, str, dict]:
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials or account unavailable")
    now = utcnow()
    email = login_email.normalize(email)
    matches = (
        await identity.by_email(session, email) if login_email.EMAIL_SHAPE.fullmatch(email) else []
    )
    enabled = [
        r for r in matches if r["access_status"] == "Active" and r["employee_status"] == "Active"
    ]
    # An ambiguous email never selects an account, so no account's lockout counter moves.
    row = enabled[0] if len(enabled) == 1 else None
    if row is not None:
        # Match the employee -> account lock order used by recovery/lifecycle.
        # Reload after locking to prevent concurrent failures losing increments.
        await lock_account_employee(session, row["account_id"])
        await session.execute(
            select(user_accounts.c.id)
            .where(user_accounts.c.id == row["account_id"])
            .with_for_update()
        )
        refreshed = await identity.by_email(session, email)
        enabled = [
            r
            for r in refreshed
            if r["access_status"] == "Active" and r["employee_status"] == "Active"
        ]
        row = (
            enabled[0]
            if len(enabled) == 1 and enabled[0]["account_id"] == row["account_id"]
            else None
        )
    if row is not None and row["locked_at"] is not None and not lock_active(row["locked_at"], now):
        await session.execute(
            update(user_accounts)
            .where(user_accounts.c.id == row["account_id"])
            .values(locked_at=None, failed_attempts=0)
        )
        await audit.record(
            session,
            actor=row["employee_id"],
            action="account.lock_expired",
            module="security",
            entity_type="user_account",
            entity_id=row["account_id"],
        )
        row = dict(row)
        row.update(locked_at=None, failed_attempts=0)
    eligible = bool(
        row
        and row["access_status"] == "Active"
        and row["employee_status"] == "Active"
        and not row["locked_at"]
        and row["password_hash"]
        and _valid_account_scope(row["designation"], row["branch_id"], row["department_id"])
    )
    encoded = row["password_hash"] if eligible and row is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(encoded, password)
    valid = eligible and password_matches
    if not valid:
        if (
            row
            and row["access_status"] == "Active"
            and row["employee_status"] == "Active"
            and not row["locked_at"]
            and _valid_account_scope(row["designation"], row["branch_id"], row["department_id"])
        ):
            failures = row["failed_attempts"] + 1
            await session.execute(
                update(user_accounts)
                .where(user_accounts.c.id == row["account_id"])
                .values(failed_attempts=failures, locked_at=now if failures >= 5 else None)
            )
            await session.execute(
                login_failures.insert().values(account_id=row["account_id"], occurred_at=now)
            )
            if failures >= 5 and row["designation"] != "Owner":
                await session.execute(
                    update(sessions)
                    .where(
                        sessions.c.account_id == row["account_id"],
                        sessions.c.invalidated_at.is_(None),
                    )
                    .values(invalidated_at=now)
                )
            await audit.record(
                session,
                actor=row["employee_id"],
                action="account.locked" if failures >= 5 else "login.failed",
                module="security",
                entity_type="user_account",
                entity_id=row["account_id"],
            )
        elif len(enabled) > 1:
            await audit.record(
                session,
                actor=None,
                action="login.failed",
                module="security",
                context={"reason": "ambiguous_email"},
            )
        else:
            await audit.record(session, actor=None, action="login.failed", module="security")
        await session.commit()
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid credentials or account unavailable")
    assert row is not None
    raw_session, raw_csrf = new_token(), new_token()
    await session.execute(
        user_accounts.update()
        .where(user_accounts.c.id == row["account_id"])
        .values(failed_attempts=0)
    )
    await session.execute(
        sessions.insert().values(
            account_id=row["account_id"],
            token_hash=token_digest(raw_session),
            csrf_hash=token_digest(raw_csrf),
            last_active_at=now,
        )
    )
    await audit.record(
        session,
        actor=row["employee_id"],
        action="login.succeeded",
        module="security",
        entity_type="user_account",
        entity_id=row["account_id"],
    )
    await session.commit()
    return raw_session, raw_csrf, dict(row)


async def resolve(session: AsyncSession, raw_session: str | None) -> Actor:
    if not raw_session:
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    digest = token_digest(raw_session)
    result = await session.execute(select(sessions).where(sessions.c.token_hash == digest))
    session_row = result.mappings().first()
    if not session_row:
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    if session_row["invalidated_at"]:
        if session_row["invalidated_at"] - session_row["last_active_at"] >= timedelta(
            seconds=settings().session_idle_seconds
        ):
            raise ApiError(401, "SESSION_EXPIRED", "Session expired")
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    now = utcnow()
    if now - session_row["last_active_at"] >= timedelta(seconds=settings().session_idle_seconds):
        await session.execute(
            update(sessions).where(sessions.c.id == session_row["id"]).values(invalidated_at=now)
        )
        await session.commit()
        raise ApiError(401, "SESSION_EXPIRED", "Session expired")
    row = await identity.by_account_id(session, session_row["account_id"])
    if (
        not row
        or row["access_status"] != "Active"
        or row["employee_status"] != "Active"
        or (row["designation"] != "Owner" and lock_active(row["locked_at"], now))
        or not _valid_account_scope(row["designation"], row["branch_id"], row["department_id"])
    ):
        await session.execute(
            update(sessions).where(sessions.c.id == session_row["id"]).values(invalidated_at=now)
        )
        await session.commit()
        raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
    await session.execute(
        update(sessions).where(sessions.c.id == session_row["id"]).values(last_active_at=now)
    )
    grants = await permission_rows.actor_grants(session, row["designation"])
    await session.commit()
    return Actor(
        row["account_id"],
        row["employee_id"],
        row["designation"],
        row["full_name"],
        row["branch_id"],
        row["department_id"],
        session_row["id"],
        session_row["csrf_hash"],
        grants,
    )


async def rotate_csrf(session: AsyncSession, actor: Actor) -> str:
    raw = new_token()
    await session.execute(
        update(sessions)
        .where(sessions.c.id == actor.session_id)
        .values(csrf_hash=token_digest(raw))
    )
    await session.commit()
    return raw


async def logout(session: AsyncSession, actor: Actor) -> None:
    await session.execute(
        update(sessions).where(sessions.c.id == actor.session_id).values(invalidated_at=utcnow())
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action="logout",
        module="security",
        entity_type="user_account",
        entity_id=actor.account_id,
    )
    await session.commit()


async def generate_link(session: AsyncSession, actor: Actor, employee_id: UUID, kind: str) -> str:
    if kind == "setup":
        require(actor, "password.setup")
    elif kind == "reset":
        require(actor, "password.reset")
    else:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid link type")
    await lock_employee(session, employee_id)
    result = await session.execute(
        select(
            user_accounts,
            employees.c.status,
            employees.c.branch_id,
            employees.c.department_id,
            designations.c.name.label("target_designation"),
        )
        .join(employees, user_accounts.c.employee_id == employees.c.id)
        .join(designations, employees.c.designation_id == designations.c.id)
        .where(employees.c.id == employee_id)
        .with_for_update(of=user_accounts)
    )
    account = result.mappings().first()
    if (
        not account
        or account["status"] == "Offboarded"
        or not _valid_account_scope(
            account["target_designation"], account["branch_id"], account["department_id"]
        )
    ):
        raise ApiError(404, "NOT_FOUND", "Record unavailable")
    require_owner_for_privileged_account(actor, account["target_designation"])
    if kind == "reset" and lock_active(account["locked_at"], utcnow()):
        require(actor, "password.locked_reset")
    if kind == "setup" and account["access_status"] != "Not Provisioned":
        raise ApiError(409, "CONFLICT", "Setup is unavailable")
    if kind == "reset" and account["access_status"] != "Active":
        raise ApiError(409, "CONFLICT", "Reset is unavailable")
    now = utcnow()
    await session.execute(
        update(password_tokens)
        .where(
            and_(
                password_tokens.c.account_id == account["id"],
                password_tokens.c.kind == kind,
                password_tokens.c.used_at.is_(None),
                password_tokens.c.invalidated_at.is_(None),
            )
        )
        .values(invalidated_at=now)
    )
    raw = new_token()
    await session.execute(
        password_tokens.insert().values(
            account_id=account["id"],
            kind=kind,
            token_hash=token_digest(raw),
            generated_by_employee_id=actor.employee_id,
            expires_at=now + timedelta(hours=24),
        )
    )
    await audit.record(
        session,
        actor=actor.employee_id,
        action=f"password.{kind}_link_generated",
        module="security",
        entity_type="user_account",
        entity_id=account["id"],
    )
    await session.commit()
    return f"{str(settings().public_origin).rstrip('/')}/{kind}-password?token={raw}"


async def complete_link(session: AsyncSession, raw_token: str, password: str, kind: str) -> None:
    digest = token_digest(raw_token)
    token_account_id = await session.scalar(
        select(password_tokens.c.account_id).where(
            password_tokens.c.token_hash == digest, password_tokens.c.kind == kind
        )
    )
    if token_account_id is None:
        raise ApiError(400, "INVALID_LINK", "Link invalid or expired")
    await lock_account_employee(session, token_account_id)
    result = await session.execute(
        select(
            user_accounts,
            employees.c.status,
            employees.c.branch_id,
            employees.c.department_id,
            designations.c.name.label("target_designation"),
        )
        .join(employees, user_accounts.c.employee_id == employees.c.id)
        .join(designations, employees.c.designation_id == designations.c.id)
        .where(user_accounts.c.id == token_account_id)
        .with_for_update(of=user_accounts)
    )
    account = result.mappings().first()
    result = await session.execute(
        select(password_tokens)
        .where(password_tokens.c.token_hash == digest, password_tokens.c.kind == kind)
        .with_for_update()
    )
    token = result.mappings().first()
    now = utcnow()
    if not token or token["used_at"] or token["invalidated_at"] or token["expires_at"] <= now:
        raise ApiError(400, "INVALID_LINK", "Link invalid or expired")
    if (
        not account
        or account["status"] == "Offboarded"
        or account["access_status"] == "Disabled"
        or not _valid_account_scope(
            account["target_designation"], account["branch_id"], account["department_id"]
        )
    ):
        raise ApiError(400, "INVALID_LINK", "Link invalid or expired")
    if account["target_designation"] in PRIVILEGED_ACCOUNT_ROLES:
        generator_role = await session.scalar(
            select(designations.c.name)
            .join(employees, employees.c.designation_id == designations.c.id)
            .where(employees.c.id == token["generated_by_employee_id"])
        )
        if generator_role != "Owner":
            raise ApiError(400, "INVALID_LINK", "Link invalid or expired")
    # Only a usable link may incur password hashing. Employee/account/token locks
    # remain held through hashing and commit, so concurrent redemption hashes once.
    encoded = hash_password(password)
    await session.execute(
        update(user_accounts)
        .where(user_accounts.c.id == token["account_id"])
        .values(password_hash=encoded, access_status="Active", failed_attempts=0, locked_at=None)
    )
    await session.execute(
        update(password_tokens).where(password_tokens.c.id == token["id"]).values(used_at=now)
    )
    await session.execute(
        update(sessions)
        .where(sessions.c.account_id == token["account_id"], sessions.c.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
    await audit.record(
        session,
        actor=account["employee_id"],
        action=f"password.{kind}_completed",
        module="security",
        entity_type="user_account",
        entity_id=account["id"],
    )
    await session.commit()


def csrf_matches(actor: Actor, supplied: str | None) -> bool:
    return bool(supplied and hmac.compare_digest(actor.csrf_hash, token_digest(supplied)))
