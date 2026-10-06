"""Standalone Case notice dispatcher; invoke independently from HTTP traffic."""

import asyncio

from app.db.session import session_factory
from app.services.case_notifications import dispatch_due


async def main() -> dict:
    async with session_factory()() as session:
        return await dispatch_due(session)


if __name__ == "__main__":
    asyncio.run(main())
