from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

import app.core.clients.model_fetcher as model_fetcher_module
from app.core.clients.model_fetcher import ModelFetchError, fetch_models_for_plan

pytestmark = pytest.mark.unit


class _TimeoutResponse:
    status = 200

    async def __aenter__(self) -> "_TimeoutResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, *, content_type: str | None = None) -> object:
        raise asyncio.TimeoutError


class _Session:
    def get(self, *args: object, **kwargs: object) -> _TimeoutResponse:
        return _TimeoutResponse()


class _VersionCache:
    async def get_version(self) -> str:
        return "0.128.0"


async def test_fetch_models_for_plan_maps_read_timeout_to_model_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.clients.model_fetcher.get_settings",
        lambda: SimpleNamespace(upstream_base_url="https://upstream.example"),
    )
    monkeypatch.setattr(
        "app.core.clients.model_fetcher.get_codex_version_cache",
        lambda: _VersionCache(),
    )

    @contextlib.asynccontextmanager
    async def lease_session():
        yield _Session()

    monkeypatch.setattr("app.core.clients.model_fetcher.lease_http_session", lease_session)

    with pytest.raises(ModelFetchError) as exc_info:
        await fetch_models_for_plan("access-token", "account-id")

    assert exc_info.value.status_code == 504
    assert exc_info.value.message == "Upstream models API timed out"
    assert exc_info.value.transport_error is True


async def test_fetch_models_for_plan_uses_account_proxy_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class Response:
        status = 200

        async def json(self, *, content_type: str | None = None) -> object:
            del content_type
            return {"models": []}

    @contextlib.asynccontextmanager
    async def account_get(local_account_id: str, url: str, **kwargs: object):
        seen.update(local_account_id=local_account_id, url=url, kwargs=kwargs)
        yield Response()

    monkeypatch.setattr(model_fetcher_module.account_proxy, "get", account_get)
    monkeypatch.setattr(
        model_fetcher_module,
        "get_settings",
        lambda: SimpleNamespace(upstream_base_url="https://upstream.example"),
    )
    monkeypatch.setattr(model_fetcher_module, "get_codex_version_cache", lambda: _VersionCache())

    @contextlib.asynccontextmanager
    async def lease_session():
        yield _Session()

    monkeypatch.setattr(model_fetcher_module, "lease_http_session", lease_session)

    result = await fetch_models_for_plan("access-token", "upstream-account", local_account_id="local-account")

    assert result == []
    assert seen["local_account_id"] == "local-account"
    assert seen["url"] == "https://upstream.example/codex/models?client_version=0.128.0"
