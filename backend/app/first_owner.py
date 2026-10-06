"""Interactive local command for one-time Owner enrollment."""

import argparse
import asyncio
import sys
from datetime import date

from sqlalchemy import func, select

from app.bootstrap import seed
from app.db.organization import designations, employees, user_accounts
from app.db.session import session_factory
from app.schemas.organization import EmployeeCreate
from app.services.first_owner import enroll


async def run() -> None:
    await seed()
    async with session_factory()() as session:
        owner_id = await session.scalar(
            select(designations.c.id).where(designations.c.name == "Owner")
        )
        if owner_id is None:
            raise RuntimeError("Locked Owner designation is unavailable")
        existing = await session.scalar(
            select(func.count())
            .select_from(employees)
            .where(employees.c.designation_id == owner_id)
        )
        accounts = await session.scalar(
            select(func.count())
            .select_from(user_accounts.join(employees))
            .where(employees.c.designation_id == owner_id)
        )
        if existing or accounts:
            raise RuntimeError("Owner enrollment refused: an Owner already exists")
        item = EmployeeCreate(
            companyEmployeeCode=input("Company Employee Code: "),
            fullName=input("Full Name: "),
            mobile=input("Mobile: "),
            personalEmail=input("Email (used to sign in): "),
            nationality=input("Nationality ISO alpha-2: "),
            gender=input("Gender (Male/Female): "),
            maritalStatus=input("Marital Status (Single/Married): "),
            dateOfJoining=date.fromisoformat(input("Date of Joining (YYYY-MM-DD): ")),
            passportNumber=input("Passport Number: "),
            emiratesIdNumber=input("Emirates ID Number (blank if absent): ") or None,
            designationId=owner_id,
        )
        _, code, link = await enroll(session, item)
    print(f"System Employee Code: {code}")
    print(f"Sign-in email: {str(item.personalEmail).lower()}")
    print(f"One-time setup link (expires in 24 hours): {link}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-local-operator", action="store_true")
    args = parser.parse_args()
    if not args.confirm_local_operator or not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("A local interactive terminal and --confirm-local-operator are required")
    asyncio.run(run())
