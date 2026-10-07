"""Interactive host-administrator recovery, authenticated by a separate offline secret."""

import argparse
import asyncio
import getpass
import os
import stat
import sys
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import settings
from app.db.base import utcnow
from app.db.organization import designations, employees, password_tokens, sessions, user_accounts
from app.db.session import session_factory
from app.security import hasher, verify_password
from app.services.privileged_access import lock_account_employee


def _secret_path() -> Path:
    path = settings().owner_recovery_secret_file
    if path is None or not path.is_absolute():
        raise RuntimeError(
            "An absolute host-only recovery verifier path must be provisioned separately"
        )
    if path.is_symlink():
        raise RuntimeError("Recovery verifier must not be a symbolic link")
    resolved = path.resolve()
    for protected in (Path(__file__).resolve().parents[2], settings().media_storage_root.resolve()):
        if resolved == protected or protected in resolved.parents:
            raise RuntimeError("Recovery verifier must be outside application source and uploads")
    return path


def _read_verifier() -> str:
    path = _secret_path()
    details = path.stat()
    if not stat.S_ISREG(details.st_mode) or details.st_size > 512:
        raise RuntimeError("Invalid recovery verifier file")
    if sys.platform != "win32" and (
        details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o077
    ):
        raise RuntimeError("Recovery verifier must belong to the host administrator and be private")
    verifier = path.read_text(encoding="ascii").strip()
    if not verifier.startswith("$argon2id$"):
        raise RuntimeError("Invalid recovery verifier")
    return verifier


async def recover(session: AsyncSession, secret: str) -> None:
    """No HTTP route or role-granted recovery: every call verifies the offline credential."""
    if len(secret) < 32 or len(secret) > 128 or not verify_password(_read_verifier(), secret):
        await audit.record(
            session, actor=None, action="account.owner_host_recovery_refused", module="security"
        )
        await session.commit()
        raise RuntimeError("Owner recovery authentication failed")
    owner_ids = (
        await session.scalars(
            select(user_accounts.c.id)
            .join(employees, employees.c.id == user_accounts.c.employee_id)
            .join(designations, designations.c.id == employees.c.designation_id)
            .where(designations.c.name == "Owner")
        )
    ).all()
    if len(owner_ids) != 1:
        raise RuntimeError("Recovery requires exactly one existing Owner account")
    account_id = owner_ids[0]
    await lock_account_employee(session, account_id)
    row = (
        (
            await session.execute(
                select(
                    user_accounts,
                    employees.c.status.label("employee_status"),
                    employees.c.branch_id,
                    employees.c.department_id,
                    designations.c.name.label("designation"),
                )
                .join(employees, employees.c.id == user_accounts.c.employee_id)
                .join(designations, designations.c.id == employees.c.designation_id)
                .where(user_accounts.c.id == account_id)
                .with_for_update(of=user_accounts)
            )
        )
        .mappings()
        .one()
    )
    if (
        row["designation"] != "Owner"
        or row["employee_status"] != "Active"
        or row["access_status"] != "Active"
        or row["branch_id"] is not None
        or row["department_id"] is not None
        or not row["password_hash"]
    ):
        raise RuntimeError("Existing Owner account is not eligible for lock recovery")
    now = utcnow()
    await session.execute(
        update(user_accounts)
        .where(user_accounts.c.id == account_id)
        .values(locked_at=None, failed_attempts=0)
    )
    await session.execute(
        update(sessions)
        .where(sessions.c.account_id == account_id, sessions.c.invalidated_at.is_(None))
        .values(invalidated_at=now)
    )
    await session.execute(
        update(password_tokens)
        .where(
            password_tokens.c.account_id == account_id,
            password_tokens.c.used_at.is_(None),
            password_tokens.c.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    await audit.record(
        session,
        actor=None,
        action="account.owner_host_recovered",
        module="security",
        entity_type="user_account",
        entity_id=account_id,
        before={"locked": row["locked_at"] is not None},
        after={"locked": False},
        context={
            "authentication": "independent_offline_credential",
            "operator": "host_administrator",
        },
    )
    await session.commit()


def provision() -> None:
    secret = getpass.getpass("New offline recovery secret (32–128 characters): ")
    confirmation = getpass.getpass("Confirm offline recovery secret: ")
    if not 32 <= len(secret) <= 128 or secret != confirmation:
        raise RuntimeError("Recovery secret must match and contain 32–128 characters")
    encoded = hasher.hash(secret)
    path = _secret_path()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as output:
            output.write(encoded + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    print("Recovery verifier provisioned. Keep the separate credential offline.")


async def run() -> None:
    secret = getpass.getpass("Offline Owner recovery secret: ")
    async with session_factory()() as session:
        await recover(session, secret)
    print("Existing Owner lock recovered; password and permissions preserved. Sign in again.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-local-operator", action="store_true")
    parser.add_argument("--provision", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local_operator or not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("A host-only interactive terminal and --confirm-local-operator are required")
    if sys.platform != "win32":
        administrator = os.geteuid() == 0
    else:
        import ctypes

        administrator = bool(ctypes.windll.shell32.IsUserAnAdmin())
    if not administrator:
        parser.error("Run as the host administrator")
    if args.provision:
        provision()
    else:
        asyncio.run(run())


if __name__ == "__main__":
    main()
