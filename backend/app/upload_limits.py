"""Bound request bodies before framework parsers allocate unbounded buffers."""

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

MAX_UPLOAD_BYTES = 5_000_000
MULTIPART_OVERHEAD_BYTES = 65_536
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
MAX_JSON_REQUEST_BYTES = 6_000_000
# These handlers enforce their own streaming limits after their security checks.
STREAMING_POST_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/setup",
    "/api/v1/auth/reset",
    "/api/v1/table-exports/csv",
}
UPLOAD_PATH = re.compile(
    r"/api/v1/(?:attendance/imports|case-imports/bank-stage(?:/validations)?|"
    r"branding/profile-banner|employees/import/(?:validate|confirm)|"
    r"employees/[^/]+/(?:media/[^/]+|documents)|"
    r"employee-documents/[^/]+/versions|catalog/[^/]+/[^/]+/image)/?\Z"
)


class UploadBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if scope.get("method") == "POST" and (
            path in STREAMING_POST_PATHS
            or (path.endswith("/") and path[:-1] in STREAMING_POST_PATHS)
        ):
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        multipart = any(
            k.lower() == b"content-type" and v.lower().startswith(b"multipart/") for k, v in headers
        )
        upload = bool(UPLOAD_PATH.fullmatch(scope.get("path", ""))) or multipart
        limit = MAX_REQUEST_BYTES if upload else MAX_JSON_REQUEST_BYTES

        async def reject() -> None:
            await JSONResponse(
                {
                    "code": "REQUEST_TOO_LARGE",
                    "message": (
                        "Upload request exceeds the size limit"
                        if upload
                        else "Request exceeds the size limit"
                    ),
                    "fieldErrors": {"file": ["Maximum file size is 5 MB"]} if upload else {},
                },
                status_code=413,
            )(scope, receive, send)

        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        maximum = str(limit).encode("ascii")
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
            if len(body) + len(chunk) > limit:
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
