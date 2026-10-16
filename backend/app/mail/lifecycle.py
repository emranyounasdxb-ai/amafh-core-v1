"""Drop retained mailbox access when the account identity or access changes.

Remote mailboxes and their messages are left untouched.
"""

from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mailbox import (
    mailbox_connections,
    mailbox_hidden_messages,
    mailbox_send_attempts,
)
from app.mail.files import purge_account_files


async def clear_secret(session: AsyncSession, account_id: UUID) -> None:
    await session.execute(
        update(mailbox_connections)
        .where(mailbox_connections.c.account_id == account_id)
        .values(secret=None, status="reconnect")
    )


async def forget_address(session: AsyncSession, account_id: UUID) -> None:
    """An Official/Login email change must not keep the previous mailbox."""
    await session.execute(
        update(mailbox_connections)
        .where(mailbox_connections.c.account_id == account_id)
        .values(
            secret=None,
            status="disconnected",
            login_email="",
            generation=mailbox_connections.c.generation + 1,
        )
    )
    await session.execute(
        delete(mailbox_hidden_messages).where(mailbox_hidden_messages.c.account_id == account_id)
    )
    await session.execute(
        delete(mailbox_send_attempts).where(mailbox_send_attempts.c.account_id == account_id)
    )
    await purge_account_files(session, account_id)
