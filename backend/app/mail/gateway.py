"""Implicit TLS IMAP and SMTP. Certificate checks stay enabled and hosts are not request input."""

import imaplib
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from app.config import settings
from app.mail.errors import MailFailure
from app.mail.folders import assign_roles

_LIST = re.compile(rb'\(([^)]*)\)\s+(?:"[^"]*"|NIL)\s+(.*)$', re.IGNORECASE)


@dataclass(frozen=True)
class FolderInfo:
    role: str
    name: str
    uid_validity: int
    unread: int


@dataclass(frozen=True)
class MessageSummary:
    uid: int
    subject: str
    sender: str
    recipients: str
    preview: str
    message_date: datetime | None
    unread: bool
    has_attachment: bool


@dataclass(frozen=True)
class AttachmentPart:
    index: int
    filename: str
    content_type: str
    size: int


@dataclass(frozen=True)
class MessageContent:
    summary: MessageSummary
    html: str
    attachments: list[AttachmentPart]
    message_id: str
    references: str
    reply_to: str
    cc: str
    bcc: str = ""


@dataclass(frozen=True)
class MessagePage:
    items: list[MessageSummary]
    total: int
    uid_validity: int


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise MailFailure("tls")
    return context


def _header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ImapSmtpGateway:
    """Talks only to the configured implicit-TLS services."""

    def verify(self, username: str, password: str) -> None:
        with self._imap(username, password):
            pass
        with self._smtp(username, password):
            pass

    def folders(self, username: str, password: str) -> list[FolderInfo]:
        with self._imap(username, password) as client:
            status, data = client.list()
            if status != "OK":
                raise MailFailure("unavailable")
            discovered = []
            for line in data or []:
                if isinstance(line, bytes):
                    parsed = _parse_list(line)
                    if parsed:
                        discovered.append(parsed)
            roles = assign_roles(discovered)
            if "inbox" not in roles:
                roles["inbox"] = "INBOX"
            result = []
            for role, name in roles.items():
                try:
                    validity, unread = self._status(client, name)
                except MailFailure:
                    continue
                result.append(FolderInfo(role, name, validity, unread))
            return result

    def unseen(self, username: str, password: str, folder_name: str, excluded: set[int]) -> int:
        with self._imap(username, password) as client:
            self._select(client, folder_name, readonly=True)
            status, data = client.uid("SEARCH", "UNSEEN")
            if status != "OK" or not data:
                return 0
            raw = data[0] if isinstance(data[0], bytes) else b""
            return sum(1 for item in raw.split() if item.isdigit() and int(item) not in excluded)

    def list_messages(
        self,
        username: str,
        password: str,
        folder_name: str,
        *,
        excluded: set[int],
        query: str,
        page: int,
        page_size: int,
    ) -> MessagePage:
        with self._imap(username, password) as client:
            validity, _unread = self._select(client, folder_name, readonly=True)
            uids = [uid for uid in self._search(client, query) if uid not in excluded]
            uids.sort(reverse=True)
            start = max(page - 1, 0) * page_size
            chosen = uids[start : start + page_size]
            return MessagePage(
                items=[self._summary(client, uid) for uid in chosen],
                total=len(uids),
                uid_validity=validity,
            )

    def message_summary(
        self, username: str, password: str, folder_name: str, uid: int
    ) -> MessageSummary:
        with self._imap(username, password) as client:
            self._select(client, folder_name, readonly=True)
            return self._summary(client, uid)

    def fetch(
        self, username: str, password: str, folder_name: str, uid: int, *, mark_seen: bool
    ) -> MessageContent:
        with self._imap(username, password) as client:
            self._select(client, folder_name, readonly=not mark_seen)
            size = self._size(client, uid)
            if size > settings().mail_read_bytes:
                summary = self._summary(client, uid)
                return MessageContent(
                    summary=summary,
                    html=(
                        "<p>This message is too large to display here. "
                        "It remains in the mailbox.</p>"
                    ),
                    attachments=[],
                    message_id="",
                    references="",
                    reply_to="",
                    cc="",
                )
            status, data = client.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = _fetch_body(data)
            if status != "OK" or raw is None:
                raise MailFailure("missing")
            if mark_seen:
                client.uid("STORE", str(uid), "+FLAGS.SILENT", "(\\Seen)")
            return _content_from_bytes(uid, raw, unread=not mark_seen)

    def fetch_attachment(
        self, username: str, password: str, folder_name: str, uid: int, index: int
    ) -> tuple[str, str, bytes]:
        content = self.fetch(username, password, folder_name, uid, mark_seen=False)
        if index < 0 or index >= len(content.attachments):
            raise MailFailure("missing")
        with self._imap(username, password) as client:
            self._select(client, folder_name, readonly=True)
            status, data = client.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = _fetch_body(data)
            if status != "OK" or raw is None:
                raise MailFailure("missing")
            message = message_from_bytes(raw)
            parts = [
                part
                for part in message.walk()
                if part.get_filename() or part.get_content_disposition() == "attachment"
            ]
            if index >= len(parts):
                raise MailFailure("missing")
            part = parts[index]
            raw_payload = part.get_payload(decode=True)
            payload = raw_payload if isinstance(raw_payload, bytes) else b""
            if len(payload) > settings().mail_read_bytes:
                raise MailFailure("too_large")
            filename = _header(part.get_filename()) or "attachment"
            return filename, part.get_content_type(), payload

    def append(
        self, username: str, password: str, folder_name: str, raw: bytes, flags: str
    ) -> tuple[int, int]:
        with self._imap(username, password) as client:
            quoted = _quote(folder_name)
            status, data = client.append(quoted, flags, None, raw)
            if status != "OK":
                raise MailFailure("append")
            validity, uid = _append_uid(data)
            if uid is None:
                token = _token_from(raw)
                self._select(client, folder_name, readonly=True)
                found = self._search(client, "", header_token=token)
                uid = found[-1] if found else None
                validity = self._status(client, folder_name)[0]
            if uid is None or validity is None:
                raise MailFailure("append")
            return validity, uid

    def send(self, username: str, password: str, recipients: list[str], raw: bytes) -> None:
        try:
            smtp = self._smtp(username, password)
        except MailFailure:
            raise
        except Exception as exc:
            raise _connect_failure(exc) from exc
        try:
            refused = smtp.sendmail(username, recipients, raw)
        except (TimeoutError, smtplib.SMTPServerDisconnected) as exc:
            raise MailFailure("unknown") from exc
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
            smtplib.SMTPResponseException,
        ) as exc:
            raise MailFailure("refused") from exc
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        if refused:
            refused_recipients = [str(address) for address in refused]
            accepted = [address for address in recipients if address not in refused_recipients]
            raise MailFailure("partial", accepted=accepted, refused=refused_recipients)

    def _imap(self, username: str, password: str) -> imaplib.IMAP4_SSL:
        _identity(username)
        current = settings()
        try:
            client = imaplib.IMAP4_SSL(
                current.mail_imap_host,
                current.mail_imap_port,
                ssl_context=tls_context(),
                timeout=current.mail_timeout_seconds,
            )
            client.login(username, password)
        except MailFailure:
            raise
        except Exception as exc:
            raise _connect_failure(exc) from exc
        return client

    def _smtp(self, username: str, password: str) -> smtplib.SMTP_SSL:
        _identity(username)
        current = settings()
        try:
            client = smtplib.SMTP_SSL(
                current.mail_smtp_host,
                current.mail_smtp_port,
                timeout=current.mail_timeout_seconds,
                context=tls_context(),
            )
            client.login(username, password)
        except MailFailure:
            raise
        except Exception as exc:
            raise _connect_failure(exc) from exc
        return client

    def _select(self, client: imaplib.IMAP4_SSL, name: str, *, readonly: bool) -> tuple[int, int]:
        status, _data = client.select(_quote(name), readonly=readonly)
        if status != "OK":
            raise MailFailure("folder")
        return self._status(client, name)

    def _status(self, client: imaplib.IMAP4_SSL, name: str) -> tuple[int, int]:
        status, data = client.status(_quote(name), "(UIDVALIDITY UNSEEN)")
        if status != "OK" or not data or not isinstance(data[0], bytes):
            raise MailFailure("folder")
        text = data[0].decode("utf-8", "replace")
        validity = _number(text, "UIDVALIDITY")
        unread = _number(text, "UNSEEN")
        if validity < 1:
            raise MailFailure("folder")
        return validity, unread

    def _search(self, client: imaplib.IMAP4_SSL, query: str, header_token: str = "") -> list[int]:
        if header_token:
            status, data = client.uid("SEARCH", "HEADER", "X-AMAFH-Token", header_token)
        elif query:
            status, data = client.uid("SEARCH", "CHARSET", "UTF-8", "TEXT", query)
        else:
            status, data = client.uid("SEARCH", "ALL")
        if status != "OK" or not data:
            return []
        raw = data[0] if isinstance(data[0], bytes) else b""
        return [int(item) for item in raw.split() if item.isdigit()]

    def _summary(self, client: imaplib.IMAP4_SSL, uid: int) -> MessageSummary:
        status, data = client.uid(
            "FETCH",
            str(uid),
            "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)] BODYSTRUCTURE)",
        )
        if status != "OK":
            raise MailFailure("missing")
        meta, header = _fetch_pair(data)
        flags = set(re.findall(r"\\[A-Za-z]+", meta))
        parsed = message_from_bytes(header or b"")
        return MessageSummary(
            uid=uid,
            subject=_header(parsed.get("Subject")),
            sender=_header(parsed.get("From")),
            recipients=_header(parsed.get("To")),
            preview=self._preview(client, uid),
            message_date=_date(parsed.get("Date")),
            unread="\\Seen" not in flags,
            has_attachment="attachment" in meta.lower() or "filename" in meta.lower(),
        )

    def _preview(self, client: imaplib.IMAP4_SSL, uid: int) -> str:
        status, data = client.uid("FETCH", str(uid), "(BODY.PEEK[TEXT]<0.180>)")
        if status != "OK":
            return ""
        _meta, body = _fetch_pair(data)
        if not body:
            return ""
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace"))
        return re.sub(r"\s+", " ", text).strip()[:180]

    def _size(self, client: imaplib.IMAP4_SSL, uid: int) -> int:
        status, data = client.uid("FETCH", str(uid), "(RFC822.SIZE)")
        if status != "OK":
            raise MailFailure("missing")
        meta, _body = _fetch_pair(data)
        return _number(meta, "RFC822.SIZE")


def _identity(username: str) -> None:
    if not username or any(mark in username for mark in ("\r", "\n", "\0")) or "@" not in username:
        raise MailFailure("auth")


def _connect_failure(exc: Exception) -> MailFailure:
    text = str(exc).lower()
    if isinstance(exc, ssl.SSLError) or "certificate" in text or "ssl" in text:
        return MailFailure("tls")
    if isinstance(exc, TimeoutError) or "timed out" in text:
        return MailFailure("timeout")
    if "auth" in text or "credential" in text or "login" in text or "authentication" in text:
        return MailFailure("auth")
    return MailFailure("unavailable")


def _parse_list(line: bytes) -> tuple[set[str], str] | None:
    match = _LIST.match(line)
    if not match:
        return None
    flags = {part.decode("ascii", "ignore") for part in match.group(1).split()}
    raw = match.group(2).strip()
    if raw.startswith(b'"') and raw.endswith(b'"'):
        name = raw[1:-1].decode("utf-8", "replace").replace('\\"', '"')
    else:
        name = raw.decode("utf-8", "replace")
    return flags, name


def _number(text: str, label: str) -> int:
    match = re.search(rf"{label}\s+(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _fetch_pair(data) -> tuple[str, bytes | None]:
    meta = ""
    body = None
    for item in data or []:
        if isinstance(item, tuple):
            meta += item[0].decode("utf-8", "replace")
            if len(item) > 1 and isinstance(item[1], bytes):
                body = item[1]
        elif isinstance(item, bytes):
            meta += item.decode("utf-8", "replace")
    return meta, body


def _fetch_body(data) -> bytes | None:
    _meta, body = _fetch_pair(data)
    return body


def _append_uid(data) -> tuple[int | None, int | None]:
    text = b" ".join(item if isinstance(item, bytes) else b"" for item in (data or []))
    match = re.search(rb"APPENDUID\s+(\d+)\s+(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _token_from(raw: bytes) -> str:
    message = message_from_bytes(raw)
    return message.get("X-AMAFH-Token", "")


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except TypeError, ValueError, IndexError:
        return None


def _content_from_bytes(uid: int, raw: bytes, *, unread: bool = True) -> MessageContent:
    message = message_from_bytes(raw)
    html = ""
    plain = ""
    attachments: list[AttachmentPart] = []
    index = 0
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part is message and message.is_multipart():
            continue
        disposition = (part.get_content_disposition() or "").lower()
        if part.get_filename() or disposition == "attachment":
            payload = part.get_payload(decode=True) or b""
            attachments.append(
                AttachmentPart(
                    index,
                    _header(part.get_filename()) or "attachment",
                    part.get_content_type(),
                    len(payload),
                )
            )
            index += 1
            continue
        if part.get_content_type() == "text/html" and not html:
            html = _part_text(part)
        elif part.get_content_type() == "text/plain" and not plain:
            plain = _part_text(part)
    if not html and plain:
        html = _plain_html(plain)
    preview_source = plain or re.sub(r"<[^>]+>", " ", html)
    preview = re.sub(r"\s+", " ", preview_source).strip()[:180]
    summary = MessageSummary(
        uid=uid,
        subject=_header(message.get("Subject")),
        sender=_header(message.get("From")),
        recipients=_header(message.get("To")),
        preview=preview,
        message_date=_date(message.get("Date")),
        unread=unread,
        has_attachment=bool(attachments),
    )
    return MessageContent(
        summary=summary,
        html=html,
        attachments=attachments,
        message_id=_header(message.get("Message-ID")),
        references=_header(message.get("References")),
        reply_to=_header(message.get("Reply-To")) or summary.sender,
        cc=_header(message.get("Cc")),
        bcc=_header(message.get("Bcc")),
    )


def _part_text(part) -> str:
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, "replace")


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _plain_html(value: str) -> str:
    text = _escape(value).replace("\r\n", "\n").replace("\n", "<br>")
    return f"<p>{text}</p>" if text else ""
