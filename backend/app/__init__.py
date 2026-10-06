"""AMAFH Core backend."""

import asyncio
import sys

if sys.platform == "win32":
    # Psycopg async connections require SelectorEventLoop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
