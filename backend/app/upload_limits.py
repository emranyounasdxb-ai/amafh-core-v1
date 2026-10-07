"""Bound upload bodies before Starlette's multipart parser creates temporary files."""

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

MAX_UPLOAD_BYTES = 5_000_000
MULTIPART_OVERHEAD_BYTES = 65_536
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
UPLOAD_PATH = re.compile(
    r"/api/v1/(?:attendance/imports|case-imports/bank-stage(?:/validations)?|"
    r"branding/profile-banner|employees/[^/]+/(?:media/[^/]+|documents)|"
    r"employee-documents/[^/]+/versions|catalog/[^/]+/[^/]+/image)/?\Z"
)


class UploadBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        multipart = any(
            k.lower() == b"content-type" and v.lower().startswith(b"multipart/") for k, v in headers
        )
        if not UPLOAD_PATH.fullmatch(scope.get("path", "")) and not multipart:
            await self.app(scope, receive, send)
            return

        async def reject() -> None:
            await JSONResponse(
                {
                    "code": "REQUEST_TOO_LARGE",
                    "message": "Upload request exceeds the size limit",
                    "fieldErrors": {"file": ["Maximum file size is 5 MB"]},
                },
                status_code=413,
            )(scope, receive, send)

        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        maximum = str(MAX_REQUEST_BYTES).encode("ascii")
        if any(
            v.isdigit()
            and (
                len(v.lstrip(b"0")) > len(maximum)
                or (len(v.lstrip(b"0")) == len(maximum) and v.lstrip(b"0") > maximum)
            )
            for v in lengths
        ):
            await reject()
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                await reject()
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
