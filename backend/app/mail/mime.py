"""Build the fully encoded outgoing message so its size can be measured."""

from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.mail.sanitize import html_to_text, sanitize_html

SAFE_TYPES = {"image", "application", "text", "audio", "video"}


def build_message(
    *,
    sender: str,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    html: str,
    attachments: list[tuple[str, str, bytes]],
    extra_headers: dict[str, str] | None = None,
    include_bcc: bool = False,
    token: str | None = None,
    message_id: str | None = None,
) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    if to:
        message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    if include_bcc and bcc:
        message["Bcc"] = ", ".join(bcc)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    domain = sender.partition("@")[2] or "localhost"
    message["Message-ID"] = message_id or make_msgid(domain=domain)
    if token:
        message["X-AMAFH-Token"] = token
    for key, value in (extra_headers or {}).items():
        if key.lower() in {"from", "to", "cc", "bcc", "subject", "message-id"}:
            continue
        if any(mark in key + value for mark in ("\r", "\n", "\0")):
            continue
        message[key] = value
    cleaned = sanitize_html(html, limit=100_000)
    message.set_content(html_to_text(cleaned) or " ")
    message.add_alternative(cleaned or "<p></p>", subtype="html")
    for filename, content_type, data in attachments:
        main, _, sub = (content_type or "").partition("/")
        if main not in SAFE_TYPES or not sub or "/" in sub:
            main, sub = "application", "octet-stream"
        message.add_attachment(
            data,
            maintype=main,
            subtype=sub.split(";")[0].strip() or "octet-stream",
            filename=filename or "attachment",
        )
    return message.as_bytes()
