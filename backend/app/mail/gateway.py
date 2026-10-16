"""Implicit TLS IMAP and SMTP. Certificate checks stay enabled and hosts are not request input."""

import base64
import codecs
import imaplib
import quopri
import re
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from urllib.parse import unquote_to_bytes

from app.config import settings
from app.mail.errors import MailFailure
from app.mail.folders import assign_roles

TRUNCATION_NOTE = "<p>The rest of this message is omitted because it exceeds the display limit.</p>"
_owned_clients: dict[int, list[object]] = {}
_owned_lock = threading.Lock()

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
class SyncHeader:
    uid: int
    subject: str
    sender: str
    recipients: str
    preview: str
    message_date: datetime | None
    unread: bool
    has_attachment: bool
    message_id: str = ""
    cc: str = ""
    bcc: str = ""
    reply_to: str = ""
    references: str = ""


@dataclass(frozen=True)
class SyncBody:
    uid: int
    html: str
    attachments: tuple[AttachmentPart, ...] = ()


@dataclass(frozen=True)
class FolderSnapshot:
    """One folder window. Bodies are text parts only; attachment bytes are absent."""

    role: str
    name: str
    uid_validity: int
    remote_uids: tuple[int, ...]
    flags: tuple[tuple[int, bool], ...]
    headers: tuple[SyncHeader, ...]
    bodies: tuple[SyncBody, ...]


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
            roles = self._folder_names(client)
            result = []
            for role, name in roles.items():
                try:
                    validity, unread = self._status(client, name)
                except MailFailure:
                    continue
                result.append(FolderInfo(role, name, validity, unread))
            return result

    def folder(self, username: str, password: str, role: str) -> FolderInfo | None:
        """Discover roles but request fresh status only for the folder being opened."""
        with self._imap(username, password) as client:
            name = self._folder_names(client).get(role)
            if name is None:
                return None
            validity, unread = self._status(client, name)
            return FolderInfo(role, name, validity, unread)

    def _folder_names(self, client: imaplib.IMAP4_SSL) -> dict[str, str]:
        status, data = client.list()
        if status != "OK":
            raise MailFailure("unavailable")
        discovered = []
        for line in data or []:
            if isinstance(line, bytes) and (parsed := _parse_list(line)):
                discovered.append(parsed)
        roles = assign_roles(discovered)
        roles.setdefault("inbox", "INBOX")
        return roles

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
                items=self._summaries(client, chosen),
                total=len(uids),
                uid_validity=validity,
            )

    def list_folder_messages(
        self,
        username: str,
        password: str,
        role: str,
        *,
        excluded_by_validity: dict[int, set[int]],
        query: str,
        page: int,
        page_size: int,
    ) -> MessagePage:
        """Discover, select and read a page within one authenticated connection."""
        with self._imap(username, password) as client:
            name = self._folder_names(client).get(role)
            if name is None:
                raise MailFailure("folder")
            validity, _unread = self._select(client, name, readonly=True)
            excluded = excluded_by_validity.get(validity, set())
            uids = [uid for uid in self._search(client, query) if uid not in excluded]
            uids.sort(reverse=True)
            start = max(page - 1, 0) * page_size
            return MessagePage(
                items=self._summaries(client, uids[start : start + page_size]),
                total=len(uids),
                uid_validity=validity,
            )

    def unread_counts(
        self,
        username: str,
        password: str,
        excluded: dict[str, dict[int, set[int]]],
    ) -> dict[str, int]:
        """One login for a refresh, retaining fresh UID validity for every folder."""
        with self._imap(username, password) as client:
            result = {}
            for role, name in self._folder_names(client).items():
                try:
                    validity, _unread = self._select(client, name, readonly=True)
                except MailFailure as exc:
                    if exc.code == "folder":
                        continue
                    raise
                status, data = client.uid("SEARCH", "UNSEEN")
                if status != "OK" or not data:
                    raise MailFailure("unavailable")
                raw = data[0] if isinstance(data[0], bytes) else b""
                hidden = excluded.get(role, {}).get(validity, set())
                result[role] = sum(
                    1 for uid in raw.split() if uid.isdigit() and int(uid) not in hidden
                )
            return result

    def snapshot_folder(
        self,
        username: str,
        password: str,
        role: str,
        *,
        known_uids: set[int],
        known_body_uids: set[int],
        header_limit: int,
        body_limit: int,
        body_bytes: int,
        previous_validity: int | None,
    ) -> FolderSnapshot | None:
        """One login. Headers for new UIDs only. Text bodies, never attachment bytes or \\Seen."""
        with self._imap(username, password) as client:
            name = self._folder_names(client).get(role)
            if name is None:
                return None
            validity, _unread = self._select(client, name, readonly=True)
            remote = self._search(client, "")
            if previous_validity not in (None, validity):
                known_uids = set()
                known_body_uids = set()
            newest = sorted(remote, reverse=True)[:header_limit]
            new_uids = [uid for uid in newest if uid not in known_uids]
            headers: list[SyncHeader] = []
            batch = max(1, settings().mail_sync_batch)
            for offset in range(0, len(new_uids), batch):
                headers.extend(self._sync_headers(client, new_uids[offset : offset + batch]))
            flag_uids = [uid for uid in remote if uid in known_uids or uid in set(newest)]
            flags = self._unread_flags(client, flag_uids, batch)
            bodies: list[SyncBody] = []
            for uid in newest[:body_limit]:
                if uid in known_body_uids:
                    continue
                html, attachments = self._peek_text(client, uid, body_bytes)
                bodies.append(SyncBody(uid=uid, html=html, attachments=tuple(attachments)))
            return FolderSnapshot(
                role=role,
                name=name,
                uid_validity=validity,
                remote_uids=tuple(sorted(remote, reverse=True)),
                flags=tuple(flags.items()),
                headers=tuple(headers),
                bodies=tuple(bodies),
            )

    def store_seen(
        self, username: str, password: str, folder_name: str, uid: int, validity: int
    ) -> None:
        """User-opened mail only. Prefetch never calls this."""
        with self._imap(username, password) as client:
            current, _unread = self._select(client, folder_name, readonly=False)
            if current != validity:
                raise MailFailure("missing")
            status, _data = client.uid("STORE", str(uid), "+FLAGS.SILENT", "(\\Seen)")
            if status != "OK":
                raise MailFailure("unavailable")

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
            return self._fetch_selected(client, uid, mark_seen=mark_seen)

    def fetch_checked(
        self, username: str, password: str, role: str, validity: int, uid: int, *, mark_seen: bool
    ) -> MessageContent:
        """One TLS login; validate fresh UIDVALIDITY before downloading or marking read."""
        with self._imap(username, password) as client:
            name = self._folder_names(client).get(role)
            if name is None:
                raise MailFailure("folder")
            current, _unread = self._select(client, name, readonly=not mark_seen)
            if current != validity:
                raise MailFailure("missing")
            return self._fetch_selected(client, uid, mark_seen=mark_seen)

    def _fetch_selected(
        self, client: imaplib.IMAP4_SSL, uid: int, *, mark_seen: bool
    ) -> MessageContent:
        size = self._size(client, uid)
        if size > settings().mail_read_bytes:
            summary = self._summary(client, uid)
            return MessageContent(
                summary=summary,
                html=(
                    "<p>This message is too large to display here. It remains in the mailbox.</p>"
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
            parts = _download_parts(message)
            if index >= len(parts):
                raise MailFailure("missing")
            part = parts[index]
            payload = _attachment_payload(part)
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
        track_connection(smtp)
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
            drop_connection(smtp)
            try:
                smtp.quit()
            except Exception:
                pass
        if refused:
            refused_recipients = [str(address) for address in refused]
            accepted = [address for address in recipients if address not in refused_recipients]
            raise MailFailure("partial", accepted=accepted, refused=refused_recipients)

    def _imap(self, username: str, password: str) -> _OwnedConnection:
        _identity(username)
        current = settings()
        try:
            client = imaplib.IMAP4_SSL(
                current.mail_imap_host,
                current.mail_imap_port,
                ssl_context=tls_context(),
                timeout=current.mail_timeout_seconds,
            )
        except MailFailure:
            raise
        except Exception as exc:
            raise _connect_failure(exc) from exc
        track_connection(client)
        try:
            client.login(username, password)
        except MailFailure:
            drop_connection(client)
            _close_client(client)
            raise
        except Exception as exc:
            drop_connection(client)
            _close_client(client)
            raise _connect_failure(exc) from exc
        return _OwnedConnection(client)

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

    def _summaries(self, client: imaplib.IMAP4_SSL, uids: list[int]) -> list[MessageSummary]:
        return [item for item, _extra in self._fetched(client, uids, composer=False)]

    def _sync_headers(self, client: imaplib.IMAP4_SSL, uids: list[int]) -> list[SyncHeader]:
        headers: list[SyncHeader] = []
        for item, extra in self._fetched(client, uids, composer=True):
            headers.append(
                SyncHeader(
                    uid=item.uid,
                    subject=item.subject,
                    sender=item.sender,
                    recipients=item.recipients,
                    preview=item.preview,
                    message_date=item.message_date,
                    unread=item.unread,
                    has_attachment=item.has_attachment,
                    message_id=extra["message_id"],
                    cc=extra["cc"],
                    bcc=extra["bcc"],
                    reply_to=extra["reply_to"] or item.sender,
                    references=extra["references"],
                )
            )
        return headers

    def _fetched(
        self, client: imaplib.IMAP4_SSL, uids: list[int], *, composer: bool
    ) -> list[tuple[MessageSummary, dict[str, str]]]:
        if not uids:
            return []
        # One bounded UID FETCH instead of a header + preview round trip per row.
        names = (
            "FROM TO CC BCC SUBJECT DATE MESSAGE-ID REPLY-TO REFERENCES "
            "CONTENT-TYPE CONTENT-TRANSFER-ENCODING"
            if composer
            else "FROM TO SUBJECT DATE CONTENT-TYPE CONTENT-TRANSFER-ENCODING"
        )
        status, data = client.uid(
            "FETCH",
            ",".join(str(uid) for uid in uids),
            f"(UID FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS ({names})] BODY.PEEK[TEXT]<0.512>)",
        )
        if status != "OK":
            raise MailFailure("unavailable")
        records = _summary_records(data)
        result: list[tuple[MessageSummary, dict[str, str]]] = []
        for uid in uids:
            record = records.get(uid)
            if record is None:
                # A message may have been expunged between SEARCH and FETCH.
                continue
            meta, header, body = record
            parsed = message_from_bytes(header)
            preview = ""
            if parsed.get_content_type() in {"text/plain", "text/html"} and body:
                preview_part = message_from_bytes(header.rstrip(b"\r\n") + b"\r\n\r\n" + body)
                try:
                    preview = _part_text(preview_part)
                except LookupError:
                    preview = body.decode("utf-8", "replace")
                if parsed.get_content_type() == "text/html":
                    preview = re.sub(r"<[^>]*>", " ", preview)
                preview = re.sub(r"\s+", " ", preview).strip()[:180]
            flag_section = re.search(r"FLAGS\s+\(([^)]*)\)", meta, re.IGNORECASE)
            flags = set(re.findall(r"\\[A-Za-z]+", flag_section.group(1) if flag_section else ""))
            sender = _header(parsed.get("From"))
            summary = MessageSummary(
                uid=uid,
                subject=_header(parsed.get("Subject")),
                sender=sender,
                recipients=_header(parsed.get("To")),
                preview=preview,
                message_date=_date(parsed.get("Date")),
                unread="\\Seen" not in flags,
                has_attachment="attachment" in meta.lower() or "filename" in meta.lower(),
            )
            result.append(
                (
                    summary,
                    {
                        "message_id": _header(parsed.get("Message-ID")),
                        "cc": _header(parsed.get("Cc")),
                        "bcc": _header(parsed.get("Bcc")),
                        "reply_to": _header(parsed.get("Reply-To")),
                        "references": _header(parsed.get("References")),
                    },
                )
            )
        return result

    def _unread_flags(
        self, client: imaplib.IMAP4_SSL, uids: list[int], batch: int
    ) -> dict[int, bool]:
        unread: dict[int, bool] = {}
        for offset in range(0, len(uids), batch):
            chunk = uids[offset : offset + batch]
            if not chunk:
                continue
            status, data = client.uid("FETCH", ",".join(str(uid) for uid in chunk), "(UID FLAGS)")
            if status != "OK":
                raise MailFailure("unavailable")
            for item in data or []:
                meta = item[0] if isinstance(item, tuple) and item else item
                if not isinstance(meta, bytes):
                    continue
                text = meta.decode("utf-8", "replace")
                uid_match = re.search(r"\bUID\s+(\d+)", text)
                if uid_match is None:
                    continue
                flags = re.search(r"FLAGS\s+\(([^)]*)\)", text, re.IGNORECASE)
                seen = bool(flags and "\\Seen" in flags.group(1))
                unread[int(uid_match.group(1))] = not seen
        return unread

    def _peek_text(
        self, client: imaplib.IMAP4_SSL, uid: int, limit: int
    ) -> tuple[str, list[AttachmentPart]]:
        """One displayable text section. Attachment bytes stay on the server."""
        status, data = client.uid("FETCH", str(uid), "(BODYSTRUCTURE)")
        structure = ""
        if status == "OK":
            meta, _body = _fetch_pair(data)
            structure = meta or ""
        tree = _parse_structure(structure)
        attachments = _attachments_from_tree(tree)
        part = _display_part(tree)
        if part is None or not part.section:
            return "<p></p>", attachments
        status, data = client.uid(
            "FETCH", str(uid), f"(BODY.PEEK[{part.section}]<0.{max(1, limit)}>)"
        )
        if status != "OK":
            return "<p></p>", attachments
        _meta, body = _fetch_pair(data)
        if not body:
            return "<p></p>", attachments
        if part.encoding in {"7BIT", "8BIT", "BINARY"} and b"\x00" in body[:32]:
            return "<p></p>", attachments
        text, truncated = _decode_transfer(
            body, part.encoding, _param(part.params, "CHARSET") or "utf-8", part.size
        )
        html = text if part.subtype == "HTML" else _plain_html(text)
        if truncated:
            html += TRUNCATION_NOTE
        return html or "<p></p>", attachments

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


def _summary_records(data) -> dict[int, tuple[str, bytes, bytes]]:
    """Associate split IMAP literals by response, even when UID is returned last."""
    records: dict[int, tuple[str, bytes, bytes]] = {}
    meta: list[str] = []
    header = b""
    body = b""

    def finish() -> None:
        combined = " ".join(meta)
        uid = _number(re.sub(r'"(?:\\.|[^"\\])*"', '""', combined), "UID")
        if uid and header:
            records[uid] = (combined, header, body)

    for item in data or []:
        raw_meta = item[0] if isinstance(item, tuple) else item
        if not isinstance(raw_meta, bytes):
            continue
        text = raw_meta.decode("utf-8", "replace")
        if re.match(r"^\d+\s+\(", text):
            finish()
            meta = []
            header = body = b""
        meta.append(text)
        if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
            if re.search(r"BODY\[HEADER\.FIELDS", text, re.IGNORECASE):
                header = item[1]
            elif re.search(r"BODY\[TEXT\]", text, re.IGNORECASE):
                body = item[1][:512]
    finish()
    return records


def _append_uid(data) -> tuple[int | None, int | None]:
    text = b" ".join(item if isinstance(item, bytes) else b"" for item in (data or []))
    match = re.search(rb"APPENDUID\s+(\d+)\s+(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _attachment_names(structure: str) -> list[AttachmentPart]:
    """MIME parts in download order. Bytes stay on the server until a download."""
    return _attachments_from_tree(_parse_structure(structure))


@dataclass
class MimePart:
    section: str
    type: str
    subtype: str
    params: list[tuple[str, str]]
    encoding: str
    size: int
    disposition: str = ""
    filename: str = ""
    children: list[MimePart] = field(default_factory=list)


class _OwnedConnection:
    """Logout the IMAP client and drop it from the timeout-abort registry."""

    def __init__(self, client: imaplib.IMAP4_SSL) -> None:
        self._client = client

    def __enter__(self) -> imaplib.IMAP4_SSL:
        return self._client

    def __exit__(self, exc_type, exc, tb) -> None:
        drop_connection(self._client)
        try:
            self._client.logout()
        except Exception:
            _close_client(self._client)


def track_connection(client: object) -> None:
    ident = threading.get_ident()
    with _owned_lock:
        _owned_clients.setdefault(ident, []).append(client)


def drop_connection(client: object) -> None:
    ident = threading.get_ident()
    with _owned_lock:
        items = _owned_clients.get(ident, [])
        if client in items:
            items.remove(client)


def abort_connections(thread_id: int) -> None:
    """Close sockets owned by a provider thread that has exceeded its wait."""
    with _owned_lock:
        clients = list(_owned_clients.get(thread_id, ()))
    for client in clients:
        _close_client(client)


def _close_client(client: object) -> None:
    shutdown = getattr(client, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
            return
        except Exception:
            pass
    closer = getattr(client, "close", None)
    if callable(closer):
        try:
            closer()
            return
        except Exception:
            pass
    sock = getattr(client, "sock", None)
    if sock is not None:
        try:
            sock.close()
        except Exception:
            pass


def _parse_value(text: str, index: int) -> tuple[object, int]:
    length = len(text)
    while index < length and text[index].isspace():
        index += 1
    if index >= length:
        return None, index
    if text[index] == "(":
        index += 1
        items: list[object] = []
        while index < length:
            while index < length and text[index].isspace():
                index += 1
            if index < length and text[index] == ")":
                return items, index + 1
            item, index = _parse_value(text, index)
            items.append(item)
        return items, index
    if text[index] == '"':
        index += 1
        chars: list[str] = []
        while index < length and text[index] != '"':
            if text[index] == "\\" and index + 1 < length:
                index += 1
            chars.append(text[index])
            index += 1
        if index < length and text[index] == '"':
            index += 1
        return "".join(chars), index
    start = index
    while index < length and not text[index].isspace() and text[index] not in "()":
        index += 1
    token = text[start:index]
    if token.upper() == "NIL":
        return None, index
    return token, index


def _parse_structure(meta: str) -> MimePart | None:
    if not meta:
        return None
    marker = meta.upper().find("BODYSTRUCTURE")
    start = marker + len("BODYSTRUCTURE") if marker >= 0 else 0
    value, _index = _parse_value(meta, start)
    if not isinstance(value, list) or not value:
        return None
    if isinstance(value[0], list):
        return _part_from(value, "")
    return _part_from(value, "1")


def _disposition_fields(value: object) -> tuple[str, list[tuple[str, str]]]:
    """body-fld-dsp is a disposition name plus parameter pairs, or NIL."""
    if not isinstance(value, list) or not value or not isinstance(value[0], str):
        return "", []
    name = value[0].upper()
    if name not in {"ATTACHMENT", "INLINE"}:
        return "", []
    return name, _pairs(value[1]) if len(value) > 1 else []


def _is_disposition(value: object) -> bool:
    name, _params = _disposition_fields(value)
    if not name or not isinstance(value, list):
        return False
    if len(value) == 1:
        return True
    return isinstance(value[1], list) or value[1] is None


def _multipart_extension(node: list, index: int) -> tuple[list[tuple[str, str]], str, str]:
    """Parameters and disposition after a multipart subtype.

    RFC 3501 places body-fld-param first and body-fld-dsp second. A server that
    omits the empty parameter list still starts with the disposition list.
    """
    params: list[tuple[str, str]] = []
    disposition = ""
    dparams: list[tuple[str, str]] = []
    if index >= len(node):
        return params, disposition, ""
    current = node[index]
    if _is_disposition(current):
        disposition, dparams = _disposition_fields(current)
        return params, disposition, _filename(params, dparams)
    if isinstance(current, list):
        params = _pairs(current)
    if index + 1 < len(node):
        disposition, dparams = _disposition_fields(node[index + 1])
    return params, disposition, _filename(params, dparams)


def _part_from(node: list, section: str) -> MimePart:
    if node and isinstance(node[0], list):
        children_raw: list[list] = []
        index = 0
        while index < len(node) and isinstance(node[index], list):
            children_raw.append(node[index])
            index += 1
        subtype = str(node[index]).upper() if index < len(node) and node[index] else "MIXED"
        params, disposition, filename = _multipart_extension(node, index + 1)
        children = [
            _part_from(child, f"{section}.{number}" if section else str(number))
            for number, child in enumerate(children_raw, start=1)
        ]
        return MimePart(
            "", "MULTIPART", subtype, params, "", 0, disposition, filename, children
        )
    type_name = str(node[0]).upper() if node and node[0] else ""
    subtype = str(node[1]).upper() if len(node) > 1 and isinstance(node[1], str) else ""
    params = _pairs(node[2]) if len(node) > 2 else []
    encoding = str(node[5]).upper() if len(node) > 5 and isinstance(node[5], str) else "7BIT"
    size = int(node[6]) if len(node) > 6 and str(node[6]).isdigit() else 0
    # message/rfc822 extensions start after the envelope, nested body, and line
    # count: index 10 is MD5 and index 11 is the disposition. Text parts put the
    # disposition at 9; every other single part puts it at 8.
    message_rfc822 = type_name == "MESSAGE" and subtype == "RFC822"
    if message_rfc822:
        disp_index = 11
    elif type_name == "TEXT":
        disp_index = 9
    else:
        disp_index = 8
    raw_disposition = node[disp_index] if len(node) > disp_index else None
    disposition, dparams = _disposition_fields(raw_disposition)
    filename = _filename(params, dparams)
    nested: list[MimePart] = []
    if message_rfc822 and len(node) > 8 and isinstance(node[8], list):
        inner = node[8]
        if inner and isinstance(inner[0], list):
            nested.append(_part_from(inner, section))
        else:
            nested.append(_part_from(inner, f"{section}.1" if section else "1"))
    return MimePart(
        section,
        type_name,
        subtype,
        params,
        encoding,
        size,
        disposition,
        filename,
        nested,
    )


def _pairs(value: object) -> list[tuple[str, str]]:
    if not isinstance(value, list):
        return []
    pairs: list[tuple[str, str]] = []
    index = 0
    while index + 1 < len(value):
        key, raw = value[index], value[index + 1]
        if isinstance(key, str) and isinstance(raw, str):
            pairs.append((key, raw))
        index += 2
    return pairs


def _param(pairs: list[tuple[str, str]], name: str) -> str:
    for key, value in pairs:
        if key.upper() == name.upper():
            return value
    return ""


def _filename(params: list[tuple[str, str]], disposition: list[tuple[str, str]]) -> str:
    continued: dict[str, list[tuple[int, str]]] = {}
    simple = ""
    encoded = False
    for key, value in [*disposition, *params]:
        match = re.match(r"(FILENAME|NAME)(?:\*(\d+))?(\*)?$", key.upper())
        if match is None:
            continue
        if match.group(2) is None and match.group(3) is None:
            simple = simple or value
            continue
        number = int(match.group(2) or 0)
        continued.setdefault(match.group(1), []).append((number, value))
        encoded = encoded or bool(match.group(3))
    for base in ("FILENAME", "NAME"):
        if base not in continued:
            continue
        raw = "".join(value for _number, value in sorted(continued[base]))
        return _rfc2231(raw) if encoded else _header(raw)
    return _header(simple) if simple else ""


def _rfc2231(value: str) -> str:
    parts = value.split("'", 2)
    if len(parts) < 3:
        return _header(value)
    charset, _language, encoded = parts
    try:
        return unquote_to_bytes(encoded).decode(charset or "utf-8", "replace")
    except LookupError:
        return unquote_to_bytes(encoded).decode("utf-8", "replace")


def _is_attachment(part: MimePart) -> bool:
    return bool(part.filename) or part.disposition == "ATTACHMENT"


def _display_part(part: MimePart | None) -> MimePart | None:
    if part is None or _is_attachment(part):
        return None
    if part.type == "MULTIPART":
        if part.subtype == "ALTERNATIVE":
            html = None
            plain = None
            for child in part.children:
                chosen = _display_part(child)
                if chosen is None:
                    continue
                if chosen.subtype == "HTML":
                    html = chosen
                elif plain is None:
                    plain = chosen
            return html or plain
        for child in part.children:
            chosen = _display_part(child)
            if chosen is not None:
                return chosen
        return None
    if part.type == "MESSAGE":
        for child in part.children:
            chosen = _display_part(child)
            if chosen is not None:
                return chosen
        return None
    if part.type == "TEXT" and part.subtype in {"PLAIN", "HTML"}:
        return part
    return None


def _attachments_from_tree(part: MimePart | None) -> list[AttachmentPart]:
    found: list[AttachmentPart] = []

    def walk(node: MimePart) -> None:
        if _is_attachment(node):
            found.append(_attachment_part(node, len(found)))
        for child in node.children:
            walk(child)

    if part is not None:
        walk(part)
    return found


def _attachment_part(part: MimePart, index: int) -> AttachmentPart:
    if part.type and part.subtype:
        content_type = f"{part.type.lower()}/{part.subtype.lower()}"
    else:
        content_type = ""
    return AttachmentPart(index, part.filename or "attachment", content_type, part.size)


def _decode_transfer(raw: bytes, encoding: str, charset: str, declared: int) -> tuple[str, bool]:
    truncated = declared > len(raw)
    enc = (encoding or "7BIT").upper()
    payload = raw
    if enc == "BASE64":
        compact = b"".join(raw.split())
        usable = len(compact) - (len(compact) % 4)
        if usable != len(compact):
            truncated = True
        try:
            payload = base64.b64decode(compact[:usable], validate=False) if usable else b""
        except Exception:
            payload = b""
            truncated = True
    elif enc == "QUOTED-PRINTABLE":
        text = raw.decode("ascii", "replace")
        if text.endswith("="):
            text = text[:-1]
            truncated = True
        elif len(text) >= 2 and text[-2] == "=" and text[-1] not in "0123456789ABCDEFabcdef":
            text = text[:-2]
            truncated = True
        payload = quopri.decodestring(text.encode("ascii", "replace"))
    try:
        decoder = codecs.getincrementaldecoder(charset or "utf-8")("ignore")
    except LookupError:
        decoder = codecs.getincrementaldecoder("utf-8")("ignore")
    decoded = decoder.decode(payload, False)
    pending = decoder.getstate()
    pending_bytes = pending[0] if isinstance(pending, tuple) and pending else b""
    if isinstance(pending_bytes, (bytes, bytearray)) and pending_bytes:
        truncated = True
    decoded += decoder.decode(b"", True)
    return decoded, truncated


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


def _is_mime_attachment(part) -> bool:
    disposition = (part.get_content_disposition() or "").lower()
    return bool(part.get_filename() or disposition == "attachment")


def _walk_message(message):
    """Yield `(part, inside_attachment, attached)` in download order."""

    def visit(part, inside: bool):
        attached = _is_mime_attachment(part)
        yield part, inside, attached
        if not part.is_multipart():
            return
        payload = part.get_payload()
        if isinstance(payload, list):
            for child in payload:
                yield from visit(child, inside or attached)

    yield from visit(message, False)


def _download_parts(message) -> list:
    """Attachment parts in the same order as the sync cache and draft retention."""
    parts = []
    for part, _inside, attached in _walk_message(message):
        if part is message and message.is_multipart() and not attached:
            continue
        if attached:
            parts.append(part)
    return parts


def _attachment_payload(part) -> bytes:
    """Bytes returned for one already-downloaded attachment.

    A leaf keeps its decoded body. ``message/rfc822`` becomes the embedded
    message. A named multipart becomes a MIME entity that still contains its
    text, nested files, and those files' decoded bytes. Synchronization does
    not call this; it never fetches attachment payloads.
    """
    main = (part.get_content_maintype() or "").lower()
    subtype = (part.get_content_subtype() or "").lower()
    if main == "message" and subtype == "rfc822":
        return _embedded_message_bytes(part)
    if main == "multipart":
        rendered = part.as_bytes()
        return rendered if isinstance(rendered, bytes) else b""
    raw = part.get_payload(decode=True)
    return raw if isinstance(raw, bytes) else b""


def _embedded_message_bytes(part) -> bytes:
    payload = part.get_payload()
    items = payload if isinstance(payload, list) else [payload]
    rendered = [item.as_bytes() for item in items if hasattr(item, "as_bytes")]
    rendered = [item for item in rendered if item]
    if len(rendered) == 1:
        return rendered[0]
    if rendered:
        return b"\r\n".join(rendered)
    own = part.as_bytes()
    return own if isinstance(own, bytes) else b""


def _content_from_bytes(uid: int, raw: bytes, *, unread: bool = True) -> MessageContent:
    message = message_from_bytes(raw)
    html = ""
    plain = ""
    attachments: list[AttachmentPart] = []
    for part, inside, attached in _walk_message(message):
        if part is message and message.is_multipart() and not attached:
            continue
        if attached:
            payload = _attachment_payload(part)
            attachments.append(
                AttachmentPart(
                    len(attachments),
                    _header(part.get_filename()) or "attachment",
                    part.get_content_type(),
                    len(payload),
                )
            )
            continue
        if inside:
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


# `<p></p>` is 7 UTF-8 bytes. Those wrappers are inside the body cap.
_PARAGRAPH_WRAPPER_BYTES = len(b"<p></p>")
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


def bound_cached_html(html: str, limit: int) -> str:
    """Fit cached HTML to `limit` UTF-8 bytes and keep the omission note.

    `limit` counts markup only. `TRUNCATION_NOTE` is appended after that budget
    and is not counted. Wrappers are inside the budget, so `<p></p>` costs
    `_PARAGRAPH_WRAPPER_BYTES` before any text. A cut stays on a code-point
    boundary, does not end inside a tag or character reference, and closes any
    element it still has open when the closer fits. If a wrapper itself does
    not fit, its text is kept within the remaining bytes. Shortened markup
    keeps the note.
    """
    source = html or ""
    omitted = TRUNCATION_NOTE in source
    body = source.replace(TRUNCATION_NOTE, "")
    if len(body.encode("utf-8")) > max(0, limit):
        body = _html_within_bytes(body, max(0, limit))
        omitted = True
    if omitted:
        return body + TRUNCATION_NOTE
    return body


def _html_within_bytes(html: str, limit: int) -> str:
    if limit < 1 or not html:
        return ""
    out: list[str] = []
    stack: list[str] = []
    used = 0
    skip = 0

    def reserved() -> int:
        return sum(len(item.encode("utf-8")) for item in stack)

    for kind, raw, name in _html_tokens(html):
        if skip:
            if kind == "open":
                skip += 1
            elif kind == "close":
                skip -= 1
            elif kind == "text":
                piece = _utf8_text_prefix(raw, limit - used - reserved())
                if not piece:
                    break
                out.append(piece)
                used += len(piece.encode("utf-8"))
                if piece != raw:
                    break
            continue
        if kind == "open":
            closer = f"</{name}>"
            cost = len(raw.encode("utf-8")) + len(closer.encode("utf-8"))
            if used + reserved() + cost > limit:
                skip = 1
                continue
            out.append(raw)
            stack.append(closer)
            used += len(raw.encode("utf-8"))
            continue
        if kind == "close":
            if stack and stack[-1].lower() == raw.lower():
                out.append(raw)
                stack.pop()
                used += len(raw.encode("utf-8"))
            elif used + reserved() + len(raw.encode("utf-8")) <= limit:
                out.append(raw)
                used += len(raw.encode("utf-8"))
            else:
                break
            continue
        if kind == "void":
            cost = len(raw.encode("utf-8"))
            if used + reserved() + cost > limit:
                break
            out.append(raw)
            used += cost
            continue
        piece = _utf8_text_prefix(raw, limit - used - reserved())
        if not piece:
            break
        out.append(piece)
        used += len(piece.encode("utf-8"))
        if piece != raw:
            break
    out.extend(reversed(stack))
    return "".join(out)


def _html_tokens(html: str):
    index = 0
    length = len(html)
    while index < length:
        if html[index] != "<":
            end = html.find("<", index)
            if end < 0:
                end = length
            yield "text", html[index:end], ""
            index = end
            continue
        end = html.find(">", index)
        if end < 0:
            yield "text", html[index:], ""
            return
        raw = html[index : end + 1]
        index = end + 1
        body = raw[1:-1].strip()
        if not body or body.startswith(("!", "?")):
            yield "void", raw, ""
            continue
        closing = body.startswith("/")
        if closing:
            body = body[1:].strip()
        tag = _tag_name(body)
        if not tag:
            yield "text", raw, ""
            continue
        if closing:
            yield "close", raw, tag
        elif tag in _VOID_TAGS or body.endswith("/"):
            yield "void", raw, tag
        else:
            yield "open", raw, tag


def _tag_name(body: str) -> str:
    name: list[str] = []
    for char in body:
        if char.isalnum() or char in "-:":
            name.append(char)
        else:
            break
    return "".join(name).lower()


def _utf8_text_prefix(text: str, limit: int) -> str:
    if limit < 1 or not text:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    out = raw[:limit].decode("utf-8", "ignore")
    marker = out.rfind("&")
    if marker >= 0 and ";" not in out[marker:]:
        out = out[:marker]
    return out
