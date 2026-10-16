"""The active mail gateway. Tests may install a fixture; production uses implicit TLS."""

import asyncio

from app.config import settings
from app.mail.gateway import ImapSmtpGateway

_gateway: ImapSmtpGateway | object | None = None
_slots = asyncio.Semaphore(4)


def set_gateway(gateway: object | None) -> None:
    global _gateway
    _gateway = gateway


def get_gateway():
    return _gateway if _gateway is not None else ImapSmtpGateway()


async def run_mail(func, /, *args, **kwargs):
    timeout = settings().mail_timeout_seconds + 5

    async with _slots:
        return await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=timeout)
