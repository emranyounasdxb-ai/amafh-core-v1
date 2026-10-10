"""Interactive host-only transition of explicitly approved existing login identities."""

import argparse
import asyncio
import sys

from sqlalchemy import select, text

from app.db.organization import employees, user_accounts
from app.db.session import session_factory
from app.services.account_access import save_login_email
from app.services.login_email import validate


async def transition(session, mappings: dict[str, str]) -> int:
    """Require an exact mapping of all unconfigured accounts, then commit atomically."""
    try:
        await session.execute(text("LOCK TABLE user_accounts IN SHARE ROW EXCLUSIVE MODE"))
        rows = (
            (
                await session.execute(
                    select(user_accounts, employees.c.company_employee_code)
                    .join(employees, employees.c.id == user_accounts.c.employee_id)
                    .where(user_accounts.c.login_email.is_(None))
                    .order_by(user_accounts.c.id)
                )
            )
            .mappings()
            .all()
        )
        if {r["company_employee_code"] for r in rows} != set(mappings):
            raise ValueError(
                "Mapping must exactly cover every unconfigured account; no writes saved"
            )
        normalized = {code: validate(email) for code, email in mappings.items()}
        for row in rows:
            await save_login_email(session, row, normalized[row["company_employee_code"]], None)
        await session.commit()
        return len(rows)
    except Exception:
        await session.rollback()
        raise


async def run() -> None:
    async with session_factory()() as session:
        rows = (
            (
                await session.execute(
                    select(employees.c.company_employee_code, employees.c.full_name)
                    .join(user_accounts, employees.c.id == user_accounts.c.employee_id)
                    .where(user_accounts.c.login_email.is_(None))
                    .order_by(employees.c.company_employee_code)
                )
            )
            .mappings()
            .all()
        )
        mappings = {}
        for row in rows:
            code = row["company_employee_code"]
            mappings[code] = validate(input(f"{code} — {row['full_name']}: Official/Login email: "))
        if not rows:
            print("No unconfigured accounts remain.")
            return
        for code, email in mappings.items():
            print(f"{code}: {email}")
        if (
            input("Type APPLY to save these explicit mappings and revoke old sessions/links: ")
            != "APPLY"
        ):
            raise RuntimeError("Transition cancelled; no writes saved")
        count = await transition(session, mappings)
        print(f"Configured {count} accounts; passwords, permissions and access states preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-local-operator", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local_operator or not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("An interactive host terminal and --confirm-local-operator are required")
    asyncio.run(run())
