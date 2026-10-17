"""Private read API. Identifiers only; no path or URL parameter is accepted."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .contract import CURSOR_EXPIRED_STATUS, MULTI_RANGE_STATUS, VERSION_MISMATCH_STATUS
from .safety import SourceChanged, SourcePending, SourceUnsafe, candidate, open_checked

_ID = re.compile(r"\A[0-9a-fA-F-]{36}\Z")
_RANGE = re.compile(r"\Abytes=(\d*)-(\d*)\Z")
_CHUNK = 65536


def token_matches(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


def content_disposition(kind: str, filename: str) -> str:
    cleaned = "".join(character if 32 < ord(character) < 127 and character not in {'"', "\\"} else "_" for character in filename)
    if not cleaned or cleaned in {".", ".."}:
        cleaned = "recording.wav"
    encoded = filename.encode("utf-8")
    from urllib.parse import quote

    return (
        f'{kind}; filename="{cleaned}"; '
        f"filename*=UTF-8''{quote(encoded.decode('utf-8'), safe='')}"
    )


def parse_single_range(header: str | None, size: int) -> tuple[int, int]:
    if header is None:
        return 0, max(size - 1, 0)
    text = header.strip()
    if "," in text:
        raise ValueError("multi")
    match = _RANGE.fullmatch(text)
    if match is None or size < 0:
        raise ValueError("bad")
    start_text, end_text = match.groups()
    if start_text == "" and end_text == "":
        raise ValueError("bad")
    if start_text == "":
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("bad")
        start = max(size - suffix, 0)
        end = size - 1
    else:
        start = int(start_text)
        end = size - 1 if end_text == "" else int(end_text)
    if start > end or start >= size:
        raise ValueError("unsatisfiable")
    return start, min(end, size - 1)


class RecordingHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AMAFHCallRecordings"

    def log_message(self, fmt, *args):
        return

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def do_GET(self):
        self._dispatch(include_body=True)

    def do_HEAD(self):
        self._dispatch(include_body=False)

    def _dispatch(self, *, include_body: bool) -> None:
        if not self._authorized():
            self._json(401, {"code": "unauthorized"})
            return
        parts = urlsplit(self.path)
        if parts.query and not parts.path.startswith("/v1/catalog/"):
            self._json(404, {"code": "not_found"})
            return
        path = parts.path
        if path == "/v1/catalog/status":
            self._json(200, self.server.app.index.status())
            return
        if path == "/v1/catalog/changes":
            self._changes(parts.query)
            return
        if path == "/v1/catalog/snapshot":
            self._snapshot(parts.query)
            return
        marker = "/v1/recordings/"
        suffix = "/content"
        if path.startswith(marker) and path.endswith(suffix):
            recording_id = path[len(marker) : -len(suffix)]
            if not _ID.fullmatch(recording_id):
                self._json(404, {"code": "not_found"})
                return
            self._content(recording_id, include_body=include_body)
            return
        self._json(404, {"code": "not_found"})

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        scheme, _, provided = header.partition(" ")
        if scheme.lower() != "bearer":
            return False
        return token_matches(provided.strip(), self.server.app.token)

    def _changes(self, query: str) -> None:
        params = _query(query)
        try:
            after = int(params.get("after", "0"))
            limit = int(params.get("limit", "200"))
        except ValueError:
            self._json(400, {"code": "invalid"})
            return
        if after < 0 or not 1 <= limit <= 500:
            self._json(400, {"code": "invalid"})
            return
        page = self.server.app.index.changes(after, limit)
        if page is None:
            self._json(CURSOR_EXPIRED_STATUS, {"code": "cursor_expired"})
            return
        self._json(200, page)

    def _snapshot(self, query: str) -> None:
        params = _query(query)
        cursor = params.get("cursor", "")
        try:
            limit = int(params.get("limit", "200"))
        except ValueError:
            self._json(400, {"code": "invalid"})
            return
        if not 1 <= limit <= 500 or len(cursor) > 80:
            self._json(400, {"code": "invalid"})
            return
        self._json(200, self.server.app.index.snapshot(cursor, limit))

    def _content(self, recording_id: str, *, include_body: bool) -> None:
        row = self.server.app.index.get(recording_id)
        if row is None or row["availability"] != "ready" or not row["file_version"]:
            self._json(404, {"code": "not_found"})
            return
        requested = self.headers.get("X-AMAFH-File-Version", "")
        if not requested:
            self._json(400, {"code": "version_required"})
            return
        month, _, filename = row["relative_path"].partition("/")
        try:
            path = candidate(self.server.app.root, month, filename)
            opened = open_checked(
                self.server.app.root_final, path, expect_version=requested
            )
        except SourceChanged:
            self._json(VERSION_MISMATCH_STATUS, {"code": "version_changed"})
            return
        except (SourceUnsafe, SourcePending, OSError):
            self._json(404, {"code": "not_found"})
            return
        try:
            size = opened.size
            range_header = self.headers.get("Range")
            if_range = self.headers.get("If-Range")
            etag = _etag(opened.version)
            use_range = bool(range_header) and (not if_range or if_range == etag)
            try:
                if size == 0:
                    start, end, status = 0, -1, 200
                elif use_range:
                    start, end = parse_single_range(range_header, size)
                    status = 206
                else:
                    start, end, status = 0, size - 1, 200
            except ValueError as exc:
                code = MULTI_RANGE_STATUS if str(exc) == "multi" else 416
                self.send_response(code)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", "0")
                self.send_header("ETag", etag)
                self._private_headers()
                self.end_headers()
                return
            length = 0 if end < start else end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("ETag", etag)
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Disposition", content_disposition("inline", row["filename"]))
            self._private_headers()
            self.end_headers()
            if not include_body or length == 0:
                return
            remaining = length
            offset = start
            while remaining:
                try:
                    payload = opened.read_at(offset, min(_CHUNK, remaining))
                except SourceChanged:
                    self.close_connection = True
                    return
                if not payload:
                    break
                try:
                    self.wfile.write(payload)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    self.close_connection = True
                    return
                offset += len(payload)
                remaining -= len(payload)
        finally:
            opened.close()

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._private_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _private_headers(self) -> None:
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")


def _etag(version: str) -> str:
    digest = hashlib.sha256(version.encode()).hexdigest()
    return f'"{digest}"'


def _query(text: str) -> dict[str, str]:
    result = {}
    if not text:
        return result
    for piece in text.split("&"):
        key, _, value = piece.partition("=")
        result.setdefault(key, value)
    return result


class RecordingServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app):
        self.app = app
        super().__init__(address, RecordingHandler)
