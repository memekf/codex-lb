from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Protocol, cast

import aiohttp

from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import AccountProxy, AccountProxyStatus
from app.modules.account_proxies.repository import AccountProxyRepository
from app.modules.account_proxies.validation import ProxyUrlValidationError, normalize_proxy_url, redact_proxy_url
from app.modules.proxy.account_cache import get_account_selection_cache

_PROXY_TEST_URL = "https://chatgpt.com/cdn-cgi/trace"
_PROXY_TEST_TIMEOUT_SECONDS = 10
_MAX_TEST_ERROR_LENGTH = 500


class AccountProxyNotFoundError(ValueError):
    pass


class AccountProxyInUseError(ValueError):
    pass


class AccountProxyValidationError(ValueError):
    pass


class ProxyTestResultLike(Protocol):
    status: str
    latency_ms: int | None
    error: str | None


@dataclass(frozen=True, slots=True)
class AccountProxyData:
    id: str
    display_name: str
    redacted_proxy_url: str
    status: str
    last_tested_at: datetime | None
    last_test_error: str | None
    last_test_latency_ms: int | None
    created_at: datetime
    updated_at: datetime
    proxy_url_changed: bool = False


@dataclass(frozen=True, slots=True)
class AccountProxyTestData:
    status: str
    last_tested_at: datetime
    last_test_error: str | None
    last_test_latency_ms: int | None


@dataclass(frozen=True, slots=True)
class ProxyTestResult:
    status: str
    latency_ms: int | None
    error: str | None


class AccountProxyService:
    def __init__(
        self,
        repository: AccountProxyRepository,
        *,
        encryptor: TokenEncryptor | None = None,
    ) -> None:
        self._repository = repository
        self._encryptor = encryptor or TokenEncryptor()

    async def list(self) -> list[AccountProxyData]:
        return [self._to_data(row) for row in await self._repository.list()]

    async def create(self, display_name: str, proxy_url: str) -> AccountProxyData:
        normalized_url = _normalize_or_raise(proxy_url)
        row = AccountProxy(
            display_name=display_name.strip(),
            proxy_url_encrypted=self._encryptor.encrypt(normalized_url),
            status=AccountProxyStatus.UNTESTED,
        )
        created = await self._repository.create(row)
        return self._to_data(created)

    async def update(self, proxy_id: str, display_name: str, proxy_url: str) -> AccountProxyData:
        row = await self._repository.get(proxy_id)
        if row is None:
            raise AccountProxyNotFoundError("Proxy not found")
        normalized_url = _normalize_or_raise(proxy_url)
        current_url = self._encryptor.decrypt(row.proxy_url_encrypted)
        row.display_name = display_name.strip()
        proxy_url_changed = normalized_url != current_url
        if proxy_url_changed:
            row.proxy_url_encrypted = self._encryptor.encrypt(normalized_url)
            row.status = AccountProxyStatus.UNTESTED
            row.last_tested_at = None
            row.last_test_error = None
            row.last_test_latency_ms = None
        updated = await self._repository.update(row)
        if proxy_url_changed:
            get_account_selection_cache().invalidate()
        return self._to_data(updated, proxy_url_changed=proxy_url_changed)

    async def delete(self, proxy_id: str) -> bool:
        row = await self._repository.get(proxy_id)
        if row is None:
            return False
        assignment_count = await self._repository.count_assignments(proxy_id)
        if assignment_count > 0:
            raise AccountProxyInUseError(f"Proxy is assigned to {assignment_count} account(s)")
        await self._repository.delete(row)
        return True

    async def test_draft(self, proxy_url: str) -> AccountProxyTestData:
        normalized_url = _normalize_or_raise(proxy_url)
        result = await test_proxy_url(normalized_url)
        return _to_test_data(result, proxy_url=normalized_url, tested_at=utcnow())

    async def test_saved(self, proxy_id: str) -> AccountProxyData:
        row = await self._repository.get(proxy_id)
        if row is None:
            raise AccountProxyNotFoundError("Proxy not found")
        proxy_url = self._encryptor.decrypt(row.proxy_url_encrypted)
        if row.status == AccountProxyStatus.FAILED and row.last_test_error is None:
            row.last_test_error = "Previous proxy test failed"
        row.status = AccountProxyStatus.TESTING
        await self._repository.update(row)
        get_account_selection_cache().invalidate()
        result = await test_proxy_url(proxy_url)
        tested_at = utcnow()
        test_data = _to_test_data(result, proxy_url=proxy_url, tested_at=tested_at)
        row.status = AccountProxyStatus(test_data.status)
        row.last_tested_at = test_data.last_tested_at
        row.last_test_error = test_data.last_test_error
        row.last_test_latency_ms = test_data.last_test_latency_ms
        updated = await self._repository.update(row)
        get_account_selection_cache().invalidate()
        return self._to_data(updated)

    def _to_data(self, row: AccountProxy, *, proxy_url_changed: bool = False) -> AccountProxyData:
        proxy_url = self._encryptor.decrypt(row.proxy_url_encrypted)
        return AccountProxyData(
            id=row.id,
            display_name=row.display_name,
            redacted_proxy_url=redact_proxy_url(proxy_url),
            status=row.status.value if isinstance(row.status, AccountProxyStatus) else str(row.status),
            last_tested_at=row.last_tested_at,
            last_test_error=row.last_test_error,
            last_test_latency_ms=row.last_test_latency_ms,
            created_at=row.created_at,
            updated_at=row.updated_at,
            proxy_url_changed=proxy_url_changed,
        )


def _normalize_or_raise(proxy_url: str) -> str:
    try:
        return normalize_proxy_url(proxy_url)
    except ProxyUrlValidationError as exc:
        raise AccountProxyValidationError(str(exc)) from exc


async def test_proxy_url(proxy_url: str) -> ProxyTestResult:
    timeout = aiohttp.ClientTimeout(total=_PROXY_TEST_TIMEOUT_SECONDS)
    started_at = time.monotonic()
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
            async with session.get(_PROXY_TEST_URL, proxy=proxy_url) as response:
                await response.read()
                latency_ms = max(0, int((time.monotonic() - started_at) * 1000))
                if response.status < 500:
                    return ProxyTestResult(status=AccountProxyStatus.WORKING.value, latency_ms=latency_ms, error=None)
                return ProxyTestResult(
                    status=AccountProxyStatus.FAILED.value,
                    latency_ms=None,
                    error=f"Proxy test target returned HTTP {response.status}",
                )
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        return ProxyTestResult(status=AccountProxyStatus.FAILED.value, latency_ms=None, error=str(exc))


def _to_test_data(result: ProxyTestResultLike, *, proxy_url: str, tested_at: datetime) -> AccountProxyTestData:
    status = _coerce_test_status(result.status)
    raw_error = result.error or ("Proxy test failed" if status == AccountProxyStatus.FAILED.value else None)
    error = _redact_test_error(raw_error, proxy_url=proxy_url) if raw_error else None
    latency_ms = result.latency_ms if status == AccountProxyStatus.WORKING.value else None
    return AccountProxyTestData(
        status=status,
        last_tested_at=tested_at,
        last_test_error=error,
        last_test_latency_ms=latency_ms,
    )


def _coerce_test_status(status: str) -> str:
    if status == AccountProxyStatus.WORKING.value:
        return AccountProxyStatus.WORKING.value
    if status == AccountProxyStatus.FAILED.value:
        return AccountProxyStatus.FAILED.value
    return AccountProxyStatus.FAILED.value


def _redact_test_error(error: str, *, proxy_url: str) -> str:
    redacted_url = redact_proxy_url(proxy_url)
    redacted = error.replace(proxy_url, redacted_url)
    parsed = SimpleNamespace(username=None, password=None)
    try:
        from urllib.parse import urlsplit

        parsed = cast(SimpleNamespace, urlsplit(proxy_url))
    except ValueError:
        parsed = SimpleNamespace(username=None, password=None)
    for credential in (parsed.username, parsed.password):
        if credential:
            redacted = redacted.replace(credential, "***")
    if len(redacted) > _MAX_TEST_ERROR_LENGTH:
        return redacted[: _MAX_TEST_ERROR_LENGTH - 3] + "..."
    return redacted
