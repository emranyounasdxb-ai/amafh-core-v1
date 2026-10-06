"""Run due Target notice dispatch as a standalone backend command."""

import asyncio
import json
import sys

from app.db.session import session_factory
from app.services.target_notifications import dispatch_due


async def run() -> dict:
    async with session_factory()() as session:
        return await dispatch_due(session)


def main() -> int:
    try:
        result = asyncio.run(run())
    except Exception:
        print("Target notification dispatch failed; transaction rolled back.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
