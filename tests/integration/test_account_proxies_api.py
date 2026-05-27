from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.crypto import TokenEncryptor
from app.db.models import AccountProxy, AccountProxyStatus
from app.db.session import SessionLocal
from app.modules.account_proxies import service as account_proxy_service
from app.modules.proxy.account_cache import get_account_selection_cache

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_account_proxy_api_crud_redacts_and_encrypts_proxy_url(async_client):
    created = await async_client.post(
        "/api/proxies",
        json={"displayName": "Primary egress", "proxyUrl": "HTTP://user:secret@Example.COM:8080"},
    )
    assert created.status_code == 200
    created_payload = created.json()
    proxy_id = created_payload["id"]
    assert created_payload["displayName"] == "Primary egress"
    assert created_payload["redactedProxyUrl"] == "http://***:***@example.com:8080"
    assert created_payload["status"] == "untested"
    assert "secret" not in str(created_payload)

    async with SessionLocal() as session:
        row = await session.get(AccountProxy, proxy_id)
        assert row is not None
        assert row.status == AccountProxyStatus.UNTESTED
        assert row.proxy_url_encrypted != b"http://user:secret@example.com:8080"
        assert TokenEncryptor().decrypt(row.proxy_url_encrypted) == "http://user:secret@example.com:8080"

    listed = await async_client.get("/api/proxies")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert [item["id"] for item in listed_payload["proxies"]] == [proxy_id]
    assert listed_payload["proxies"][0]["redactedProxyUrl"] == "http://***:***@example.com:8080"

    updated = await async_client.put(
        f"/api/proxies/{proxy_id}",
        json={"displayName": "Backup egress", "proxyUrl": "https://user:newpass@example.net:8443"},
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["displayName"] == "Backup egress"
    assert updated_payload["redactedProxyUrl"] == "https://***:***@example.net:8443"
    assert "newpass" not in str(updated_payload)

    deleted = await async_client.delete(f"/api/proxies/{proxy_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    final = await async_client.get("/api/proxies")
    assert final.status_code == 200
    assert final.json()["proxies"] == []


@pytest.mark.asyncio
async def test_account_proxy_api_rejects_invalid_proxy_url(async_client):
    response = await async_client.post(
        "/api/proxies",
        json={"displayName": "Invalid", "proxyUrl": "socks5://example.com:1080"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_proxy_url"


@pytest.mark.asyncio
async def test_account_proxy_api_tests_draft_without_persisting(async_client, monkeypatch):
    seen_proxy_urls: list[str] = []

    async def fake_test_proxy_url(proxy_url: str):
        seen_proxy_urls.append(proxy_url)
        return SimpleNamespace(status="working", latency_ms=42, error=None)

    monkeypatch.setattr(account_proxy_service, "test_proxy_url", fake_test_proxy_url, raising=False)

    tested = await async_client.post(
        "/api/proxies/test",
        json={"proxyUrl": "https://user:secret@example.com:8443"},
    )

    assert tested.status_code == 200
    payload = tested.json()
    assert payload["status"] == "working"
    assert payload["lastTestLatencyMs"] == 42
    assert payload["lastTestError"] is None
    assert "secret" not in str(payload)
    assert seen_proxy_urls == ["https://user:secret@example.com:8443"]

    async with SessionLocal() as session:
        rows = (await session.execute(select(AccountProxy))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_account_proxy_api_tests_saved_proxy_and_persists_redacted_failure(async_client, monkeypatch):
    async def fake_test_proxy_url(proxy_url: str):
        assert proxy_url == "https://user:secret@example.com:8443"
        return SimpleNamespace(status="failed", latency_ms=None, error=f"cannot connect via {proxy_url}")

    monkeypatch.setattr(account_proxy_service, "test_proxy_url", fake_test_proxy_url, raising=False)

    created = await async_client.post(
        "/api/proxies",
        json={"displayName": "Primary egress", "proxyUrl": "https://user:secret@example.com:8443"},
    )
    proxy_id = created.json()["id"]
    selection_cache = get_account_selection_cache()
    generation_before_test = selection_cache.generation

    tested = await async_client.post(f"/api/proxies/{proxy_id}/test")

    assert tested.status_code == 200
    assert selection_cache.generation > generation_before_test
    payload = tested.json()
    assert payload["id"] == proxy_id
    assert payload["status"] == "failed"
    assert payload["lastTestedAt"] is not None
    assert payload["lastTestLatencyMs"] is None
    assert "secret" not in str(payload)
    assert payload["lastTestError"] == "cannot connect via https://***:***@example.com:8443"

    async with SessionLocal() as session:
        row = await session.get(AccountProxy, proxy_id)
        assert row is not None
        assert row.status == AccountProxyStatus.FAILED
        assert row.last_tested_at is not None
        assert row.last_test_latency_ms is None
        assert row.last_test_error == "cannot connect via https://***:***@example.com:8443"


@pytest.mark.asyncio
async def test_account_proxy_api_exposes_testing_status_without_erasing_previous_failed_result(
    async_client, monkeypatch
):
    async def fail_test(_proxy_url: str):
        return SimpleNamespace(status="failed", latency_ms=None, error="previous failure")

    monkeypatch.setattr(account_proxy_service, "test_proxy_url", fail_test, raising=False)
    created = await async_client.post(
        "/api/proxies",
        json={"displayName": "Retest egress", "proxyUrl": "https://proxy.example.com:8443"},
    )
    proxy_id = created.json()["id"]
    first_test = await async_client.post(f"/api/proxies/{proxy_id}/test")
    assert first_test.json()["status"] == "failed"

    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_test(_proxy_url: str):
        started.set()
        await release.wait()
        return SimpleNamespace(status="working", latency_ms=12, error=None)

    monkeypatch.setattr(account_proxy_service, "test_proxy_url", blocking_test, raising=False)
    retest = asyncio.create_task(async_client.post(f"/api/proxies/{proxy_id}/test"))
    await started.wait()

    listed = await async_client.get("/api/proxies")
    in_progress = next(item for item in listed.json()["proxies"] if item["id"] == proxy_id)
    assert in_progress["status"] == "testing"
    assert in_progress["lastTestError"] == "previous failure"

    release.set()
    completed = await retest
    assert completed.json()["status"] == "working"
