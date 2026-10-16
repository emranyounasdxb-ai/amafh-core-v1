"""The active mail gateway. Tests may install a fixture; production uses implicit TLS."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.mail.gateway import ImapSmtpGateway, abort_connections

_gateway: ImapSmtpGateway | object | None = None
# Interactive reads stay separate from the single background sync operation.
_slots = asyncio.Semaphore(4)
_sync_slots = asyncio.Semaphore(1)
_mail_pool: ThreadPoolExecutor | None = None
_sync_pool: ThreadPoolExecutor | None = None


def set_gateway(gateway: object | None) -> None:
    global _gateway
    _gateway = gateway


def get_gateway():
    return _gateway if _gateway is not None else ImapSmtpGateway()


def _pool(sync: bool) -> ThreadPoolExecutor:
    global _mail_pool, _sync_pool
    if sync:
        if _sync_pool is None:
            _sync_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mail-sync")
        return _sync_pool
    if _mail_pool is None:
        _mail_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mail")
    return _mail_pool


def shutdown_mail_runtime() -> None:
    """Stop accepting provider work. A thread already inside a socket cannot be killed."""
    global _mail_pool, _sync_pool
    for pool in (_mail_pool, _sync_pool):
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
    _mail_pool = None
    _sync_pool = None


async def run_mail(func, /, *args, **kwargs):
    return await _run_owned(_slots, _pool(False), func, args, kwargs)


async def run_sync(func, /, *args, **kwargs):
    """One background mailbox job at a time, outside the interactive slot pool."""
    return await _run_owned(_sync_slots, _pool(True), func, args, kwargs)


async def _run_owned(semaphore, executor, func, args, kwargs):
    """Hold the slot until the provider thread finishes, including after a timeout."""
    timeout = settings().mail_timeout_seconds + 5
    await semaphore.acquire()
    loop = asyncio.get_running_loop()
    ident: dict[str, int] = {}

    def call():
        ident["thread"] = threading.get_ident()
        return func(*args, **kwargs)

    future = loop.run_in_executor(executor, call)
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout)
    except TimeoutError:
        thread_id = ident.get("thread")
        if thread_id is not None:
            abort_connections(thread_id)
        raise
    finally:
        if future.done():
            semaphore.release()
        else:
            future.add_done_callback(lambda _future: loop.call_soon_threadsafe(semaphore.release))
