"""Pull metadata and open one recording stream. Redirects are not followed."""

import contextlib
from collections.abc import AsyncIterator

import httpx

from app.calls.contract import CONTRACT_VERSION
from app.config import settings


class ConnectorFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def outbound_configured() -> bool:
    current = settings()
    return bool(
        current.calls_enabled and current.calls_connector_url and current.calls_connector_token
    )


def transfer_configured() -> bool:
    """Whether a direct recording URL may contact the connector.

    Calls disabled, or enabled without a connector address and token, is
    rejected before any request. Replacing the HTTP client does not bypass
    this check.
    """
    return outbound_configured()


def _timeout() -> httpx.Timeout:
    current = settings()
    return httpx.Timeout(
        connect=current.calls_connect_timeout_seconds,
        read=current.calls_stream_idle_seconds,
        write=10,
        pool=current.calls_connect_timeout_seconds,
    )


def _client() -> httpx.AsyncClient:
    current = settings()
    return httpx.AsyncClient(
        base_url=current.calls_connector_url.rstrip("/"),
        timeout=_timeout(),
        follow_redirects=False,
        trust_env=False,
        headers={"Authorization": f"Bearer {current.calls_connector_token}"},
    )


async def _payload(response: httpx.Response) -> dict:
    if 300 <= response.status_code < 400:
        raise ConnectorFailure("unavailable")
    if response.status_code == 410:
        raise ConnectorFailure("cursor_expired")
    if response.status_code == 401:
        raise ConnectorFailure("auth")
    if response.status_code != 200:
        raise ConnectorFailure("unavailable")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ConnectorFailure("contract") from exc
    if payload.get("contractVersion") != CONTRACT_VERSION:
        raise ConnectorFailure("contract")
    return payload


async def get_status() -> dict:
    async with _client() as client:
        try:
            response = await client.get("/v1/catalog/status")
        except httpx.HTTPError as exc:
            raise ConnectorFailure("unavailable") from exc
        return await _payload(response)


async def get_changes(after: int, limit: int) -> dict:
    async with _client() as client:
        try:
            response = await client.get(
                "/v1/catalog/changes", params={"after": after, "limit": limit}
            )
        except httpx.HTTPError as exc:
            raise ConnectorFailure("unavailable") from exc
        return await _payload(response)


async def get_snapshot(cursor: str, limit: int) -> dict:
    async with _client() as client:
        try:
            response = await client.get(
                "/v1/catalog/snapshot", params={"cursor": cursor, "limit": limit}
            )
        except httpx.HTTPError as exc:
            raise ConnectorFailure("unavailable") from exc
        return await _payload(response)


async def open_content(
    connector_id: str,
    version: str,
    headers: dict[str, str],
    *,
    method: str = "GET",
) -> tuple[httpx.AsyncClient, httpx.Response]:
    if method not in {"GET", "HEAD"}:
        raise ConnectorFailure("unavailable")
    client = _client()
    response = None
    request_headers = {"X-AMAFH-File-Version": version, **headers}
    try:
        request = client.build_request(
            method, f"/v1/recordings/{connector_id}/content", headers=request_headers
        )
        try:
            response = await client.send(request, stream=True)
        except httpx.HTTPError as exc:
            raise ConnectorFailure("unavailable") from exc
        if 300 <= response.status_code < 400:
            raise ConnectorFailure("unavailable")
        delivered = (client, response)
        client = None
        response = None
        return delivered
    finally:
        if response is not None:
            with contextlib.suppress(Exception):
                await response.aclose()
        if client is not None:
            with contextlib.suppress(Exception):
                await client.aclose()


async def iter_bytes(response: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in response.aiter_bytes(settings().calls_stream_chunk_bytes):
        yield chunk
