from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp_retry import RetryClient
from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as websockets_connect_impl

from app.core.clients.http import lease_http_client, lease_http_session, lease_retry_client
from app.core.crypto import TokenEncryptor
from app.db.models import Account, AccountProxyStatus, AccountStatus
from app.db.session import SessionLocal
from app.modules.account_proxies.validation import ProxyUrlValidationError, normalize_proxy_url, redact_proxy_url


@dataclass(frozen=True, slots=True)
class AccountProxyTransport:
    proxy_url: str | None
    proxy_fingerprint: str


class AccountProxyTransportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def resolve_transport(account_id: str) -> AccountProxyTransport:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Account).options(selectinload(Account.proxy)).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise AccountProxyTransportError("account_not_found", "Account was not found")
        if account.status == AccountStatus.PAUSED:
            raise AccountProxyTransportError("account_paused", "Account is paused")
        if account.status == AccountStatus.DEACTIVATED:
            raise AccountProxyTransportError("account_deactivated", "Account is deactivated")
        if account.proxy_id is None:
            return AccountProxyTransport(proxy_url=None, proxy_fingerprint="none")

        proxy = account.proxy
        if proxy is None:
            raise AccountProxyTransportError("proxy_missing", "Assigned proxy was not found")
        status = proxy.status.value if isinstance(proxy.status, AccountProxyStatus) else str(proxy.status)
        if status == AccountProxyStatus.FAILED.value or (
            status == AccountProxyStatus.TESTING.value and proxy.last_test_error is not None
        ):
            raise AccountProxyTransportError("proxy_failed", "Assigned proxy is marked failed")
        try:
            proxy_url = normalize_proxy_url(TokenEncryptor().decrypt(proxy.proxy_url_encrypted))
        except InvalidToken as exc:
            raise AccountProxyTransportError("proxy_decrypt_failed", "Assigned proxy could not be decrypted") from exc
        except ProxyUrlValidationError as exc:
            raise AccountProxyTransportError("proxy_invalid", "Assigned proxy URL is invalid") from exc

        return AccountProxyTransport(
            proxy_url=proxy_url,
            proxy_fingerprint=_proxy_fingerprint(proxy.id, proxy_url),
        )


@asynccontextmanager
async def request(
    account_id: str,
    method: str,
    url: str,
    *,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> AsyncIterator[aiohttp.ClientResponse]:
    transport = await resolve_transport(account_id)
    request_kwargs = _apply_proxy(kwargs, transport.proxy_url)
    if session is not None:
        request_method = getattr(session, "request", None)
        if callable(request_method):
            context = request_method(method, url, **request_kwargs)
        else:
            method_specific = getattr(session, method.lower())
            context = method_specific(url, **request_kwargs)
        async with context as response:
            yield response
        return

    async with lease_http_session() as client_session:
        async with client_session.request(method, url, **request_kwargs) as response:
            yield response


def get(
    account_id: str,
    url: str,
    *,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> AsyncIterator[aiohttp.ClientResponse]:
    return request(account_id, "GET", url, session=session, **kwargs)


def post(
    account_id: str,
    url: str,
    *,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> AsyncIterator[aiohttp.ClientResponse]:
    return request(account_id, "POST", url, session=session, **kwargs)


@asynccontextmanager
async def retry_request(
    account_id: str,
    method: str,
    url: str,
    *,
    client: RetryClient | None = None,
    **kwargs: Any,
) -> AsyncIterator[aiohttp.ClientResponse]:
    transport = await resolve_transport(account_id)
    request_kwargs = _apply_proxy(kwargs, transport.proxy_url)
    async with lease_retry_client(client) as retry_client:
        async with retry_client.request(method, url, **request_kwargs) as response:
            yield response


async def ws_connect(
    account_id: str,
    url: str,
    *,
    session: aiohttp.ClientSession | None = None,
    **kwargs: Any,
) -> aiohttp.ClientWebSocketResponse:
    transport = await resolve_transport(account_id)
    request_kwargs = _apply_proxy(kwargs, transport.proxy_url)
    if session is not None:
        return await session.ws_connect(url, **request_kwargs)

    async with lease_http_client() as client:
        return await client.websocket_session.ws_connect(url, **request_kwargs)


async def websockets_connect(
    account_id: str,
    url: str,
    **kwargs: Any,
) -> ClientConnection:
    transport = await resolve_transport(account_id)
    request_kwargs = _apply_proxy(kwargs, transport.proxy_url)
    return await websockets_connect_impl(url, **request_kwargs)


def _apply_proxy(kwargs: dict[str, Any], proxy_url: str | None) -> dict[str, Any]:
    if proxy_url is None:
        return kwargs
    next_kwargs = dict(kwargs)
    next_kwargs["proxy"] = proxy_url
    return next_kwargs


def _proxy_fingerprint(proxy_id: str, proxy_url: str) -> str:
    digest = hashlib.sha256(proxy_url.encode("utf-8")).hexdigest()[:16]
    return f"proxy:{proxy_id}:{digest}"


def redact_transport_error(error: AccountProxyTransportError) -> str:
    return redact_proxy_url(error.message)
