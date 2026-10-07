"""Bounded, per-process authentication limits keyed by the socket peer, not headers."""

import math
import time
from collections import deque
from threading import Lock

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class AuthThrottle:
    WINDOW_SECONDS = 60
    MAX_CLIENTS = 10_000
    MAX_BODY_BYTES = 4096
    ROUTES = {
        "/api/v1/auth/login": ("login", 10),
        "/api/v1/auth/setup": ("completion", 5),
        "/api/v1/auth/reset": ("completion", 5),
    }

    def __init__(self, app: ASGIApp):
        self.app = app
        self._requests: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    def admit(self, group: str, client: str, limit: int) -> int:
        key = (group, client)
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.WINDOW_SECONDS
            if len(self._requests) >= self.MAX_CLIENTS:
                self._requests = {k: v for k, v in self._requests.items() if v and v[-1] > cutoff}
            if key not in self._requests and len(self._requests) >= self.MAX_CLIENTS:
                return self.WINDOW_SECONDS
            bucket = self._requests.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, math.ceil(bucket[0] + self.WINDOW_SECONDS - now))
            bucket.append(now)
        return 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        route = self.ROUTES.get(scope.get("path", ""))
        if scope["type"] != "http" or scope.get("method") != "POST" or route is None:
            await self.app(scope, receive, send)
            return
        peer = scope.get("client")
        retry = self.admit(route[0], peer[0] if peer else "unknown", route[1])
        if retry:
            await JSONResponse(
                {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests. Retry later.",
                    "fieldErrors": {},
                },
                status_code=429,
                headers={"Retry-After": str(retry)},
            )(scope, receive, send)
            return
        # Bound the JSON body before parsing, including chunked requests. Never
        # retain request bodies or account identifiers in the limiter.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.MAX_BODY_BYTES:
                await JSONResponse(
                    {
                        "code": "REQUEST_TOO_LARGE",
                        "message": "Request exceeds the size limit",
                        "fieldErrors": {},
                    },
                    status_code=413,
                )(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        payload = bytes(body)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
