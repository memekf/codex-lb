from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import anyio
import pytest
from sqlalchemy import text

import app.modules.proxy.service as proxy_module
from app.core.clients import account_proxy
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import (
    Account,
    AccountActiveTimeframe,
    AccountActiveTimeframeMode,
    AccountProxy,
    AccountProxyStatus,
    AccountStatus,
)
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class _FakeResponse:
    status: int = 200


class _RequestContext:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, *_: object) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _RequestContext:
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        return _RequestContext(_FakeResponse())


@pytest.mark.asyncio
async def test_account_proxy_transport_applies_resolved_proxy(db_setup):
    del db_setup
    account_id = "account-with-proxy"
    proxy_url = "https://user:secret@example.com:8443"
    async with SessionLocal() as session:
        proxy = AccountProxy(
            id="proxy-transport",
            display_name="Transport",
            proxy_url_encrypted=TokenEncryptor().encrypt(proxy_url),
            status=AccountProxyStatus.WORKING,
        )
        session.add(proxy)
        session.add(_account(account_id, proxy_id=proxy.id))
        await session.commit()

    fake_session = _FakeSession()

    async with account_proxy.request(
        account_id,
        "POST",
        "https://upstream.example.test/responses",
        session=fake_session,
        json={"model": "gpt-test"},
    ) as response:
        assert response.status == 200

    assert fake_session.calls == [
        {
            "method": "POST",
            "url": "https://upstream.example.test/responses",
            "kwargs": {
                "json": {"model": "gpt-test"},
                "proxy": proxy_url,
            },
        }
    ]
    transport = await account_proxy.resolve_transport(account_id)
    assert transport.proxy_url == proxy_url
    assert transport.proxy_fingerprint.startswith("proxy:proxy-transport:")


@pytest.mark.asyncio
async def test_account_proxy_transport_keeps_direct_account_direct(db_setup):
    del db_setup
    account_id = "direct-account"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=None))
        await session.commit()

    fake_session = _FakeSession()

    async with account_proxy.get(
        account_id,
        "https://upstream.example.test/models",
        session=fake_session,
    ):
        pass

    assert fake_session.calls == [
        {
            "method": "GET",
            "url": "https://upstream.example.test/models",
            "kwargs": {},
        }
    ]
    transport = await account_proxy.resolve_transport(account_id)
    assert transport.proxy_url is None
    assert transport.proxy_fingerprint == "none"


@pytest.mark.asyncio
async def test_account_proxy_transport_rejects_failed_proxy_without_request(db_setup):
    del db_setup
    account_id = "failed-proxy-account"
    async with SessionLocal() as session:
        proxy = AccountProxy(
            id="failed-proxy",
            display_name="Failed",
            proxy_url_encrypted=TokenEncryptor().encrypt("https://failed.example.com:8443"),
            status=AccountProxyStatus.FAILED,
        )
        session.add(proxy)
        session.add(_account(account_id, proxy_id=proxy.id))
        await session.commit()

    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.post(
            account_id,
            "https://upstream.example.test/responses",
            session=fake_session,
            json={},
        ):
            pass

    assert exc_info.value.code == "proxy_failed"
    assert fake_session.calls == []


@pytest.mark.asyncio
async def test_account_proxy_transport_rejects_previously_failed_proxy_during_retest(db_setup):
    del db_setup
    account_id = "retesting-failed-proxy-account"
    async with SessionLocal() as session:
        proxy = AccountProxy(
            id="retesting-failed-proxy",
            display_name="Retesting failed",
            proxy_url_encrypted=TokenEncryptor().encrypt("https://failed.example.com:8443"),
            status=AccountProxyStatus.TESTING,
            last_tested_at=utcnow(),
            last_test_error="previous failure",
        )
        session.add(proxy)
        session.add(_account(account_id, proxy_id=proxy.id))
        await session.commit()

    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.post(
            account_id,
            "https://upstream.example.test/responses",
            session=fake_session,
            json={},
        ):
            pass

    assert exc_info.value.code == "proxy_failed"
    assert fake_session.calls == []


@pytest.mark.asyncio
async def test_account_proxy_transport_rejects_missing_account_without_request(db_setup):
    del db_setup
    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.get("missing-account", "https://upstream.example.test/models", session=fake_session):
            pass

    assert exc_info.value.code == "account_not_found"
    assert fake_session.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (AccountStatus.PAUSED, "account_paused"),
        (AccountStatus.DEACTIVATED, "account_deactivated"),
    ],
)
async def test_account_proxy_transport_rejects_disabled_account_without_request(db_setup, status, expected_code):
    del db_setup
    account_id = f"disabled-{status.value}-account"
    account = _account(account_id, proxy_id=None)
    account.status = status
    async with SessionLocal() as session:
        session.add(account)
        await session.commit()
    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.get(account_id, "https://upstream.example.test/models", session=fake_session):
            pass

    assert exc_info.value.code == expected_code
    assert fake_session.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("missing", "proxy_missing"),
        ("invalid", "proxy_invalid"),
        ("undecryptable", "proxy_decrypt_failed"),
    ],
)
async def test_account_proxy_transport_rejects_unusable_assignment_without_request(db_setup, kind, expected_code):
    del db_setup
    account_id = f"{kind}-assigned-proxy-account"
    proxy_id = f"{kind}-assigned-proxy"
    async with SessionLocal() as session:
        if kind == "missing":
            await session.execute(text("PRAGMA foreign_keys=OFF"))
        else:
            encrypted_url = (
                TokenEncryptor().encrypt("socks5://proxy.example.com:1080")
                if kind == "invalid"
                else b"not-encrypted"
            )
            session.add(
                AccountProxy(
                    id=proxy_id,
                    display_name=kind,
                    proxy_url_encrypted=encrypted_url,
                    status=AccountProxyStatus.WORKING,
                )
            )
        session.add(_account(account_id, proxy_id=proxy_id))
        await session.commit()
        if kind == "missing":
            await session.execute(text("PRAGMA foreign_keys=ON"))

    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.get(account_id, "https://upstream.example.test/models", session=fake_session):
            pass

    assert exc_info.value.code == expected_code
    assert fake_session.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["outside", "invalid", "missing"])
async def test_account_proxy_transport_rejects_unavailable_active_timeframe_without_request(db_setup, kind):
    del db_setup
    account_id = f"{kind}-active-timeframe-account"
    timeframe_id = f"{kind}-active-timeframe"
    async with SessionLocal() as session:
        if kind == "missing":
            await session.execute(text("PRAGMA foreign_keys=OFF"))
        else:
            tomorrow = (utcnow().weekday() + 1) % 7
            session.add(
                AccountActiveTimeframe(
                    id=timeframe_id,
                    display_name=kind,
                    timezone="Not/AZone" if kind == "invalid" else "UTC",
                    start_minute=0,
                    end_minute=0,
                    mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
                    weekdays=json.dumps([tomorrow]),
                    random_seed=f"seed-{kind}",
                )
            )
        session.add(_account(account_id, proxy_id=None, active_timeframe_id=timeframe_id))
        await session.commit()
        if kind == "missing":
            await session.execute(text("PRAGMA foreign_keys=ON"))

    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.get(account_id, "https://upstream.example.test/models", session=fake_session):
            pass

    assert exc_info.value.code == "account_outside_active_timeframe"
    assert fake_session.calls == []


@pytest.mark.asyncio
async def test_account_proxy_transport_rejects_malformed_active_timeframe_weekdays_without_request(db_setup):
    del db_setup
    account_id = "malformed-active-timeframe-account"
    timeframe_id = "malformed-active-timeframe"
    async with SessionLocal() as session:
        session.add(
            AccountActiveTimeframe(
                id=timeframe_id,
                display_name="malformed",
                timezone="UTC",
                start_minute=0,
                end_minute=0,
                mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
                weekdays="{not-json",
                random_seed="seed-malformed",
            )
        )
        session.add(_account(account_id, proxy_id=None, active_timeframe_id=timeframe_id))
        await session.commit()

    fake_session = _FakeSession()

    with pytest.raises(account_proxy.AccountProxyTransportError) as exc_info:
        async with account_proxy.get(account_id, "https://upstream.example.test/models", session=fake_session):
            pass

    assert exc_info.value.code == "account_outside_active_timeframe"
    assert fake_session.calls == []


@pytest.mark.asyncio
async def test_transport_fingerprint_resolution_keeps_existing_sessions_soft_across_timeframe_boundary(db_setup):
    del db_setup
    account_id = "soft-existing-timeframe-account"
    tomorrow = (utcnow().weekday() + 1) % 7
    async with SessionLocal() as session:
        session.add(
            AccountActiveTimeframe(
                id="soft-existing-timeframe",
                display_name="Outside",
                timezone="UTC",
                start_minute=0,
                end_minute=0,
                mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
                weekdays=json.dumps([tomorrow]),
                random_seed="seed-soft",
            )
        )
        session.add(_account(account_id, proxy_id=None, active_timeframe_id="soft-existing-timeframe"))
        await session.commit()

    fingerprint = await proxy_module._resolve_account_transport_fingerprint(account_id)

    assert fingerprint == "none"


def _account(account_id: str, *, proxy_id: str | None, active_timeframe_id: str | None = None) -> Account:
    now = utcnow()
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        chatgpt_account_id=f"upstream-{account_id}",
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-token"),
        refresh_token_encrypted=encryptor.encrypt("refresh-token"),
        id_token_encrypted=encryptor.encrypt("id-token"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        proxy_id=proxy_id,
        active_timeframe_id=active_timeframe_id,
    )


@pytest.mark.asyncio
async def test_account_proxy_assignment_closes_local_http_bridge_sessions(async_client, app_instance, db_setup):
    del db_setup
    account_id = "bridge-account"
    other_account_id = "other-bridge-account"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=None))
        session.add(_account(other_account_id, proxy_id=None))
        await session.commit()
    proxy = await async_client.post(
        "/api/proxies",
        json={"displayName": "Bridge proxy", "proxyUrl": "https://bridge.example.com:8443"},
    )
    assert proxy.status_code == 200

    service = get_proxy_service_for_app(app_instance)
    target_key = proxy_module._HTTPBridgeSessionKey("session_header", "session-target", None)
    other_key = proxy_module._HTTPBridgeSessionKey("session_header", "session-other", None)
    target_session = _dummy_bridge_session(target_key, account_id)
    other_session = _dummy_bridge_session(other_key, other_account_id)
    async with service._http_bridge_lock:
        service._http_bridge_sessions[target_key] = cast(proxy_module._HTTPBridgeSession, target_session)
        service._http_bridge_sessions[other_key] = cast(proxy_module._HTTPBridgeSession, other_session)

    assigned = await async_client.put(f"/api/accounts/{account_id}/proxy", json={"proxyId": proxy.json()["id"]})

    assert assigned.status_code == 200
    assert target_session.closed is True
    assert other_session.closed is False
    async with service._http_bridge_lock:
        assert target_key not in service._http_bridge_sessions
        assert service._http_bridge_sessions[other_key] is other_session


@pytest.mark.asyncio
async def test_managed_proxy_url_update_closes_assigned_local_http_bridge_sessions(
    async_client, app_instance, db_setup
):
    del db_setup
    proxy = await async_client.post(
        "/api/proxies",
        json={"displayName": "Original proxy", "proxyUrl": "https://original.example.com:8443"},
    )
    assert proxy.status_code == 200
    proxy_id = proxy.json()["id"]
    account_id = "proxy-url-bridge-account"
    other_account_id = "direct-bridge-account"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=proxy_id))
        session.add(_account(other_account_id, proxy_id=None))
        await session.commit()

    service = get_proxy_service_for_app(app_instance)
    target_key = proxy_module._HTTPBridgeSessionKey("session_header", "session-proxy-url-target", None)
    other_key = proxy_module._HTTPBridgeSessionKey("session_header", "session-proxy-url-other", None)
    target_session = _dummy_bridge_session(target_key, account_id, proxy_id=proxy_id)
    other_session = _dummy_bridge_session(other_key, other_account_id, proxy_id=None)
    async with service._http_bridge_lock:
        service._http_bridge_sessions[target_key] = cast(proxy_module._HTTPBridgeSession, target_session)
        service._http_bridge_sessions[other_key] = cast(proxy_module._HTTPBridgeSession, other_session)

    updated = await async_client.put(
        f"/api/proxies/{proxy_id}",
        json={"displayName": "Updated proxy", "proxyUrl": "https://updated.example.com:8443"},
    )

    assert updated.status_code == 200
    assert target_session.closed is True
    assert other_session.closed is False
    async with service._http_bridge_lock:
        assert target_key not in service._http_bridge_sessions
        assert service._http_bridge_sessions[other_key] is other_session


@pytest.mark.asyncio
async def test_native_upstream_websocket_connect_uses_local_account_transport(app_instance, db_setup, monkeypatch):
    del db_setup
    account = _account("native-websocket-account", proxy_id=None)
    seen: dict[str, object] = {}
    upstream = _FakeNativeUpstreamWebSocket()

    async def fake_connect_responses_websocket(
        headers: dict[str, str],
        access_token: str,
        upstream_account_id: str | None,
        *,
        local_account_id: str,
    ):
        seen["headers"] = headers
        seen["access_token"] = access_token
        seen["upstream_account_id"] = upstream_account_id
        seen["local_account_id"] = local_account_id
        return upstream

    monkeypatch.setattr(proxy_module, "connect_responses_websocket", fake_connect_responses_websocket)

    service = get_proxy_service_for_app(app_instance)
    connected = await service._open_upstream_websocket(account, {"session_id": "session-native"})

    assert connected is upstream
    assert seen == {
        "headers": {"session_id": "session-native"},
        "access_token": "access-token",
        "upstream_account_id": "upstream-native-websocket-account",
        "local_account_id": "native-websocket-account",
    }


@pytest.mark.asyncio
async def test_http_bridge_reuse_rejects_stale_proxy_fingerprint(app_instance, async_client, db_setup, monkeypatch):
    del db_setup
    account_id = "stale-fingerprint-account"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=None))
        await session.commit()
    proxy = await async_client.post(
        "/api/proxies",
        json={"displayName": "Stale check", "proxyUrl": "https://stale.example.com:8443"},
    )
    assert proxy.status_code == 200
    proxy_id = proxy.json()["id"]
    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        account.proxy_id = proxy_id
        await session.commit()

    service = get_proxy_service_for_app(app_instance)
    key = proxy_module._HTTPBridgeSessionKey("session_header", "session-stale-fingerprint", None)
    stale_session = _dummy_bridge_session(key, account_id, proxy_id=None, proxy_fingerprint="none")
    replacement_session = _dummy_bridge_session(key, account_id, proxy_id=proxy_id, proxy_fingerprint="replacement")
    async with service._http_bridge_lock:
        service._http_bridge_sessions[key] = cast(proxy_module._HTTPBridgeSession, stale_session)

    async def fake_create_http_bridge_session(*args, **kwargs):
        del args, kwargs
        return cast(proxy_module._HTTPBridgeSession, replacement_session)

    async def fake_claim_durable_http_bridge_session(*args, **kwargs):
        del args, kwargs
        return None

    monkeypatch.setattr(service, "_create_http_bridge_session", fake_create_http_bridge_session)
    monkeypatch.setattr(service, "_claim_durable_http_bridge_session", fake_claim_durable_http_bridge_session)
    monkeypatch.setattr(proxy_module, "_http_bridge_owner_check_required", lambda *_, **__: False)

    result = await service._get_or_create_http_bridge_session(
        key,
        headers={},
        affinity=proxy_module._AffinityPolicy(key="session-stale-fingerprint", kind="session_header"),
        api_key=None,
        request_model="gpt-5.4",
        idle_ttl_seconds=120.0,
        max_sessions=2,
    )

    assert result is replacement_session
    assert stale_session.closed is True
    async with service._http_bridge_lock:
        assert service._http_bridge_sessions[key] is replacement_session


@pytest.mark.asyncio
async def test_http_bridge_submit_rejects_stale_proxy_fingerprint_before_send(
    app_instance,
    db_setup,
    monkeypatch,
):
    del db_setup
    account_id = "stale-submit-account"
    proxy_id = "stale-submit-proxy"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=None))
        session.add(
            AccountProxy(
                id=proxy_id,
                display_name="Submit proxy",
                proxy_url_encrypted=TokenEncryptor().encrypt("https://submit.example.com:8443"),
                status=AccountProxyStatus.WORKING,
            )
        )
        await session.commit()

    service = get_proxy_service_for_app(app_instance)
    key = proxy_module._HTTPBridgeSessionKey("session_header", "session-stale-submit", None)
    upstream = _RecordingUpstreamWebSocket()
    stale_session = _dummy_bridge_session(
        key,
        account_id,
        proxy_id=None,
        proxy_fingerprint="none",
        upstream=upstream,
    )
    async with service._http_bridge_lock:
        service._http_bridge_sessions[key] = cast(proxy_module._HTTPBridgeSession, stale_session)

    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        account.proxy_id = proxy_id
        await session.commit()

    async def fail_if_prewarmed(*args, **kwargs):
        del args, kwargs
        raise AssertionError("stale transport must be rejected before prewarm")

    monkeypatch.setattr(service, "_maybe_prewarm_http_bridge_session", fail_if_prewarmed)
    request_state = proxy_module._WebSocketRequestState(
        request_id="request-stale-submit",
        model="gpt-5.4",
        service_tier=None,
        reasoning_effort=None,
        api_key_reservation=None,
        started_at=time.monotonic(),
        request_text='{"type":"response.create"}',
        transport="http",
    )

    with pytest.raises(proxy_module.ProxyResponseError) as exc_info:
        await service._submit_http_bridge_request(
            cast(proxy_module._HTTPBridgeSession, stale_session),
            request_state=request_state,
            text_data='{"type":"response.create"}',
            queue_limit=1,
        )

    assert exc_info.value.status_code == 502
    assert upstream.sent_texts == []
    assert upstream.closed is True
    assert stale_session.closed is True
    async with service._http_bridge_lock:
        assert key not in service._http_bridge_sessions


@pytest.mark.asyncio
async def test_native_websocket_rejects_stale_proxy_fingerprint_before_send(
    app_instance,
    db_setup,
    monkeypatch,
):
    del db_setup
    account_id = "native-stale-send-account"
    proxy_id = "native-stale-send-proxy"
    async with SessionLocal() as session:
        session.add(_account(account_id, proxy_id=None))
        session.add(
            AccountProxy(
                id=proxy_id,
                display_name="Native stale proxy",
                proxy_url_encrypted=TokenEncryptor().encrypt("https://native-stale.example.com:8443"),
                status=AccountProxyStatus.WORKING,
            )
        )
        await session.commit()

    service = get_proxy_service_for_app(app_instance)
    upstream = _RecordingUpstreamWebSocket()
    downstream = _StaleNativeDownstreamWebSocket(account_id=account_id, proxy_id=proxy_id)

    async def fake_connect_proxy_websocket(*args, **kwargs):
        del args, kwargs
        return _account(account_id, proxy_id=None), upstream

    async def fake_relay_upstream_websocket_messages(*args, **kwargs):
        del args, kwargs
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "_connect_proxy_websocket", fake_connect_proxy_websocket)
    monkeypatch.setattr(service, "_relay_upstream_websocket_messages", fake_relay_upstream_websocket_messages)

    await service.proxy_responses_websocket(
        downstream,
        {},
        codex_session_affinity=False,
        openai_cache_affinity=False,
        api_key=None,
    )

    assert len(upstream.sent_texts) == 1
    assert upstream.sent_bytes == []
    assert upstream.closed is True
    emitted_events = [json.loads(text) for text in downstream.sent_texts]
    assert emitted_events[-1]["type"] == "response.failed"
    assert emitted_events[-1]["response"]["error"]["code"] == "upstream_unavailable"


class _FakeNativeUpstreamWebSocket:
    async def send_text(self, text: str) -> None:
        del text

    async def send_bytes(self, data: bytes) -> None:
        del data

    async def receive(self) -> object:
        return SimpleNamespace(kind="close", close_code=1000)

    async def close(self) -> None:
        return None

    def response_header(self, name: str) -> str | None:
        del name
        return None


class _RecordingUpstreamWebSocket:
    def __init__(self) -> None:
        self.sent_texts: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.closed = False

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self) -> object:
        await asyncio.Event().wait()

    async def close(self) -> None:
        self.closed = True


class _StaleNativeDownstreamWebSocket:
    def __init__(self, *, account_id: str, proxy_id: str) -> None:
        self._account_id = account_id
        self._proxy_id = proxy_id
        self._receive_count = 0
        self.sent_texts: list[str] = []

    async def receive(self) -> dict[str, object]:
        self._receive_count += 1
        if self._receive_count == 1:
            return {
                "type": "websocket.receive",
                "text": json.dumps(
                    {
                        "type": "response.create",
                        "model": "gpt-5.4",
                        "instructions": "",
                        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
                        "stream": True,
                    },
                    separators=(",", ":"),
                ),
            }
        if self._receive_count == 2:
            async with SessionLocal() as session:
                account = await session.get(Account, self._account_id)
                assert account is not None
                account.proxy_id = self._proxy_id
                await session.commit()
            return {"type": "websocket.receive", "bytes": b"must-not-send"}
        return {"type": "websocket.disconnect"}

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason


def _dummy_bridge_session(
    session_key: proxy_module._HTTPBridgeSessionKey,
    account_id: str,
    *,
    proxy_id: str | None = None,
    proxy_fingerprint: str = "none",
    upstream: object | None = None,
) -> SimpleNamespace:
    async def _close() -> None:
        return None

    if upstream is None:
        upstream = SimpleNamespace(close=_close)

    return SimpleNamespace(
        key=session_key,
        headers={},
        closed=False,
        account=SimpleNamespace(id=account_id, status=AccountStatus.ACTIVE, proxy_id=proxy_id),
        request_model="gpt-5.4",
        pending_lock=anyio.Lock(),
        pending_requests=[],
        queued_request_count=0,
        last_used_at=time.monotonic(),
        idle_ttl_seconds=120.0,
        codex_session=False,
        downstream_turn_state=None,
        downstream_turn_state_aliases=set(),
        previous_response_ids=set(),
        durable_session_id=None,
        durable_owner_epoch=None,
        upstream_reader=None,
        upstream_control=proxy_module._WebSocketUpstreamControl(),
        upstream=upstream,
        response_create_gate=asyncio.Semaphore(1),
        proxy_fingerprint=proxy_fingerprint,
    )
