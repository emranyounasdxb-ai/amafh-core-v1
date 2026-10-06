"""Run approved Task due notices independently of HTTP requests."""

import asyncio
import json

from app.db.session import session_factory
from app.services.task_notifications import dispatch_due


async def main() -> None:
    async with session_factory()() as session:
        result = await dispatch_due(session)
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
