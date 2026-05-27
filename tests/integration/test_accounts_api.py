from __future__ import annotations

import base64
import json

import pytest

from app.core.auth import generate_unique_account_id, parse_auth_json
from app.core.utils.time import utcnow
from app.db.models import AccountActiveTimeframe, AccountProxy, AccountProxyStatus
from app.db.session import SessionLocal
from app.modules.proxy.account_cache import get_account_selection_cache

pytestmark = pytest.mark.integration


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


def _auth_json(*, email: str, raw_account_id: str) -> dict:
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    return {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }


async def _import_account(async_client, *, email: str, raw_account_id: str) -> str:
    auth_json = _auth_json(email=email, raw_account_id=raw_account_id)
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200
    return expected_account_id


async def _create_timeframe(async_client) -> str:
    response = await async_client.post(
        "/api/active-timeframes",
        json={
            "displayName": "Office hours",
            "timezone": "UTC",
            "startTime": "09:00",
            "endTime": "17:00",
            "mode": "fixed_weekdays",
            "weekdays": [0, 1, 2, 3, 4],
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.mark.asyncio
async def test_import_and_list_accounts(async_client):
    email = "tester@example.com"
    raw_account_id = "acc_explicit"
    payload = {
        "email": email,
        "chatgpt_account_id": "acc_payload",
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }

    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["accountId"] == expected_account_id
    assert data["email"] == email
    assert data["planType"] == "plus"

    list_response = await async_client.get("/api/accounts")
    assert list_response.status_code == 200
    accounts = list_response.json()["accounts"]
    assert any(account["accountId"] == expected_account_id for account in accounts)
    matched = next(account for account in accounts if account["accountId"] == expected_account_id)
    assert matched["proxyId"] is None
    assert matched["proxyDisplayName"] is None
    assert matched["proxyRedactedUrl"] is None
    assert matched["proxyStatus"] is None
    assert matched["proxyAvailability"] == "direct"
    assert matched["proxyAvailabilityReason"] == "none"
    assert matched["activeTimeframeId"] is None
    assert matched["activeTimeframeDisplayName"] is None
    assert matched["activeTimeframeAvailability"] == "always"
    assert matched["activeTimeframeAvailabilityReason"] == "none"


@pytest.mark.asyncio
async def test_set_clear_and_preserve_account_active_timeframe(async_client):
    email = "timeframe-account@example.com"
    raw_account_id = "acc_timeframe"
    account_id = await _import_account(async_client, email=email, raw_account_id=raw_account_id)
    timeframe_id = await _create_timeframe(async_client)
    selection_cache = get_account_selection_cache()
    generation_before_assignment = selection_cache.generation

    assigned = await async_client.put(
        f"/api/accounts/{account_id}/active-timeframe",
        json={"activeTimeframeId": timeframe_id},
    )

    assert assigned.status_code == 200
    assert assigned.json() == {"status": "updated", "activeTimeframeId": timeframe_id}
    assert selection_cache.generation > generation_before_assignment

    accounts = await async_client.get("/api/accounts")
    assert accounts.status_code == 200
    matched = next(account for account in accounts.json()["accounts"] if account["accountId"] == account_id)
    assert matched["activeTimeframeId"] == timeframe_id
    assert matched["activeTimeframeDisplayName"] == "Office hours"
    assert matched["activeTimeframeMode"] == "fixed_weekdays"
    assert matched["activeTimeframeTimezone"] == "UTC"
    assert matched["activeTimeframeWindow"] == "09:00-17:00"
    assert matched["activeTimeframeWeekdays"] == [0, 1, 2, 3, 4]
    assert matched["activeTimeframeResolvedWeekdays"] == [0, 1, 2, 3, 4]
    assert matched["activeTimeframeAvailability"] in {"active", "inactive"}
    assert matched["activeTimeframeAvailabilityReason"] in {"none", "outside_window"}
    assert "activeTimeframeNextChangeAt" in matched

    files = {
        "auth_json": (
            "auth.json",
            json.dumps(_auth_json(email=email, raw_account_id=raw_account_id)),
            "application/json",
        )
    }
    imported_again = await async_client.post("/api/accounts/import", files=files)
    assert imported_again.status_code == 200

    accounts_after_import = await async_client.get("/api/accounts")
    matched_after_import = next(
        account for account in accounts_after_import.json()["accounts"] if account["accountId"] == account_id
    )
    assert matched_after_import["activeTimeframeId"] == timeframe_id

    exported = await async_client.post(f"/api/accounts/{account_id}/export")
    assert exported.status_code == 200
    exported_auth = json.loads(exported.json()["authJson"])
    assert "active_timeframe_id" not in json.dumps(exported_auth)
    assert "activeTimeframeId" not in json.dumps(exported_auth)

    generation_before_clear = selection_cache.generation
    cleared = await async_client.put(
        f"/api/accounts/{account_id}/active-timeframe",
        json={"activeTimeframeId": None},
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"status": "updated", "activeTimeframeId": None}
    assert selection_cache.generation > generation_before_clear


@pytest.mark.asyncio
async def test_list_accounts_returns_invalid_metadata_for_malformed_active_timeframe_weekdays(async_client):
    email = "malformed-timeframe-account@example.com"
    raw_account_id = "acc_malformed_timeframe"
    account_id = await _import_account(async_client, email=email, raw_account_id=raw_account_id)
    timeframe_id = await _create_timeframe(async_client)

    assigned = await async_client.put(
        f"/api/accounts/{account_id}/active-timeframe",
        json={"activeTimeframeId": timeframe_id},
    )
    assert assigned.status_code == 200

    async with SessionLocal() as session:
        timeframe = await session.get(AccountActiveTimeframe, timeframe_id)
        assert timeframe is not None
        timeframe.weekdays = "{not-json"
        await session.commit()

    accounts = await async_client.get("/api/accounts")

    assert accounts.status_code == 200
    matched = next(account for account in accounts.json()["accounts"] if account["accountId"] == account_id)
    assert matched["activeTimeframeId"] == timeframe_id
    assert matched["activeTimeframeDisplayName"] == "Office hours"
    assert matched["activeTimeframeAvailability"] == "invalid"
    assert matched["activeTimeframeAvailabilityReason"] == "timeframe_invalid"


@pytest.mark.asyncio
async def test_set_account_active_timeframe_rejects_missing_account_or_timeframe(async_client):
    account_id = await _import_account(
        async_client,
        email="missing-timeframe@example.com",
        raw_account_id="acc_missing_timeframe",
    )

    missing_timeframe = await async_client.put(
        f"/api/accounts/{account_id}/active-timeframe",
        json={"activeTimeframeId": "missing-timeframe"},
    )
    assert missing_timeframe.status_code == 404
    assert missing_timeframe.json()["error"]["code"] == "active_timeframe_not_found"

    missing_account = await async_client.put(
        "/api/accounts/missing-account/active-timeframe",
        json={"activeTimeframeId": None},
    )
    assert missing_account.status_code == 404
    assert missing_account.json()["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_reactivate_missing_account_returns_404(async_client):
    response = await async_client.post("/api/accounts/missing/reactivate")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_pause_missing_account_returns_404(async_client):
    response = await async_client.post("/api/accounts/missing/pause")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_pause_account(async_client):
    email = "pause@example.com"
    raw_account_id = "acc_pause"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }

    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200

    pause = await async_client.post(f"/api/accounts/{expected_account_id}/pause")
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"

    accounts = await async_client.get("/api/accounts")
    assert accounts.status_code == 200
    data = accounts.json()["accounts"]
    matched = next((account for account in data if account["accountId"] == expected_account_id), None)
    assert matched is not None
    assert matched["status"] == "paused"


@pytest.mark.asyncio
async def test_update_account_limit_warmup_opt_in(async_client):
    email = "warmup@example.com"
    raw_account_id = "acc_warmup"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }

    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200

    update = await async_client.put(f"/api/accounts/{expected_account_id}/limit-warmup", json={"enabled": True})
    assert update.status_code == 200
    assert update.json() == {"status": "enabled", "enabled": True}

    accounts = await async_client.get("/api/accounts")
    assert accounts.status_code == 200
    data = accounts.json()["accounts"]
    matched = next((account for account in data if account["accountId"] == expected_account_id), None)
    assert matched is not None
    assert matched["limitWarmupEnabled"] is True
    assert matched["limitWarmup"] is None


@pytest.mark.asyncio
async def test_export_account_returns_latest_codex_auth_json_with_no_store_headers(async_client):
    email = "export@example.com"
    raw_account_id = "acc_export"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }

    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200

    export = await async_client.post(f"/api/accounts/{expected_account_id}/export")
    assert export.status_code == 200
    assert export.headers["cache-control"] == "no-store, no-cache, must-revalidate, private"
    assert export.headers["pragma"] == "no-cache"
    assert export.headers["expires"] == "0"

    payload = export.json()
    assert payload["accountId"] == expected_account_id
    assert payload["email"] == email
    assert payload["planType"] == "plus"
    assert payload["status"] == "active"

    parsed_auth = parse_auth_json(payload["authJson"].encode("utf-8"))
    assert parsed_auth.tokens.access_token == "access"
    assert parsed_auth.tokens.refresh_token == "refresh"
    assert parsed_auth.tokens.account_id == raw_account_id
    assert parsed_auth.last_refresh_at is not None


@pytest.mark.asyncio
async def test_export_missing_account_returns_404(async_client):
    response = await async_client.post("/api/accounts/missing/export")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_delete_missing_account_returns_404(async_client):
    response = await async_client.delete("/api/accounts/missing")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_set_alias_missing_account_returns_404(async_client):
    response = await async_client.put("/api/accounts/missing/alias", json={"alias": "Personal Plus"})
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "account_not_found"


@pytest.mark.asyncio
async def test_set_and_clear_account_alias(async_client):
    email = "alias@example.com"
    raw_account_id = "acc_alias"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }

    expected_account_id = generate_unique_account_id(raw_account_id, email)
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200

    # Default summary uses the email since no alias is set yet.
    listing = await async_client.get("/api/accounts")
    matched = next(a for a in listing.json()["accounts"] if a["accountId"] == expected_account_id)
    assert matched["alias"] is None
    assert matched["displayName"] == email


@pytest.mark.asyncio
async def test_set_and_clear_account_proxy_assignment(async_client):
    email = "proxy-assignment@example.com"
    raw_account_id = "acc_proxy_assignment"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    response = await async_client.post(
        "/api/accounts/import",
        files={"auth_json": ("auth.json", json.dumps(auth_json), "application/json")},
    )
    assert response.status_code == 200

    proxy = await async_client.post(
        "/api/proxies",
        json={"displayName": "Primary egress", "proxyUrl": "https://user:secret@example.com:8443"},
    )
    assert proxy.status_code == 200
    proxy_id = proxy.json()["id"]

    assigned = await async_client.put(f"/api/accounts/{expected_account_id}/proxy", json={"proxyId": proxy_id})
    assert assigned.status_code == 200
    assert assigned.json() == {"status": "updated", "proxyId": proxy_id}

    listing = await async_client.get("/api/accounts")
    matched = next(account for account in listing.json()["accounts"] if account["accountId"] == expected_account_id)
    assert matched["proxyId"] == proxy_id
    assert matched["proxyDisplayName"] == "Primary egress"
    assert matched["proxyRedactedUrl"] == "https://***:***@example.com:8443"
    assert matched["proxyStatus"] == "untested"
    assert matched["proxyAvailability"] == "warning"
    assert matched["proxyAvailabilityReason"] == "proxy_untested"

    async with SessionLocal() as session:
        row = await session.get(AccountProxy, proxy_id)
        assert row is not None
        row.status = AccountProxyStatus.TESTING
        row.last_tested_at = utcnow()
        row.last_test_error = "previous failure"
        await session.commit()

    listing = await async_client.get("/api/accounts")
    matched = next(account for account in listing.json()["accounts"] if account["accountId"] == expected_account_id)
    assert matched["proxyStatus"] == "testing"
    assert matched["proxyAvailability"] == "unavailable"
    assert matched["proxyAvailabilityReason"] == "proxy_failed"

    delete_assigned = await async_client.delete(f"/api/proxies/{proxy_id}")
    assert delete_assigned.status_code == 409
    assert delete_assigned.json()["error"]["code"] == "proxy_in_use"

    cleared = await async_client.put(f"/api/accounts/{expected_account_id}/proxy", json={"proxyId": None})
    assert cleared.status_code == 200
    assert cleared.json() == {"status": "updated", "proxyId": None}

    listing = await async_client.get("/api/accounts")
    matched = next(account for account in listing.json()["accounts"] if account["accountId"] == expected_account_id)
    assert matched["proxyId"] is None
    assert matched["proxyAvailability"] == "direct"
    assert matched["proxyAvailabilityReason"] == "none"


@pytest.mark.asyncio
async def test_set_account_proxy_rejects_missing_proxy(async_client):
    email = "missing-proxy@example.com"
    raw_account_id = "acc_missing_proxy"
    payload = {
        "email": email,
        "chatgpt_account_id": raw_account_id,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
    }
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(payload),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": raw_account_id,
        },
    }
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    response = await async_client.post(
        "/api/accounts/import",
        files={"auth_json": ("auth.json", json.dumps(auth_json), "application/json")},
    )
    assert response.status_code == 200

    missing = await async_client.put(f"/api/accounts/{expected_account_id}/proxy", json={"proxyId": "missing"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "proxy_not_found"


@pytest.mark.asyncio
async def test_reimport_preserves_proxy_assignment_and_export_is_proxy_free(async_client):
    settings = await async_client.put(
        "/api/settings",
        json={
            "stickyThreadsEnabled": False,
            "preferEarlierResetAccounts": False,
            "importWithoutOverwrite": False,
            "totpRequiredOnLogin": False,
        },
    )
    assert settings.status_code == 200

    email = "proxy-preserve@example.com"
    raw_account_id = "acc_proxy_preserve"
    expected_account_id = generate_unique_account_id(raw_account_id, email)
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(
                {
                    "email": email,
                    "chatgpt_account_id": raw_account_id,
                    "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
                }
            ),
            "accessToken": "access-one",
            "refreshToken": "refresh-one",
            "accountId": raw_account_id,
        },
    }
    imported = await async_client.post(
        "/api/accounts/import",
        files={"auth_json": ("auth.json", json.dumps(auth_json), "application/json")},
    )
    assert imported.status_code == 200

    proxy = await async_client.post(
        "/api/proxies",
        json={"displayName": "Primary egress", "proxyUrl": "https://user:secret@example.com:8443"},
    )
    proxy_id = proxy.json()["id"]
    assigned = await async_client.put(f"/api/accounts/{expected_account_id}/proxy", json={"proxyId": proxy_id})
    assert assigned.status_code == 200

    auth_json["tokens"]["accessToken"] = "access-two"
    reimported = await async_client.post(
        "/api/accounts/import",
        files={"auth_json": ("auth.json", json.dumps(auth_json), "application/json")},
    )
    assert reimported.status_code == 200
    assert reimported.json()["accountId"] == expected_account_id

    listing = await async_client.get("/api/accounts")
    matched = next(account for account in listing.json()["accounts"] if account["accountId"] == expected_account_id)
    assert matched["proxyId"] == proxy_id

    exported = await async_client.post(f"/api/accounts/{expected_account_id}/export")
    assert exported.status_code == 200
    exported_auth = json.loads(exported.json()["authJson"])
    assert "proxyId" not in exported_auth
    assert "proxy_id" not in exported_auth
    assert "proxyUrl" not in exported_auth
    assert "proxy_url" not in exported_auth

    # Setting an alias updates both `alias` and `displayName`.
    set_response = await async_client.put(
        f"/api/accounts/{expected_account_id}/alias",
        json={"alias": "  Personal Plus  "},
    )
    assert set_response.status_code == 200
    body = set_response.json()
    assert body["alias"] == "Personal Plus"  # whitespace-trimmed
    listing = await async_client.get("/api/accounts")
    matched = next(a for a in listing.json()["accounts"] if a["accountId"] == expected_account_id)
    assert matched["alias"] == "Personal Plus"
    assert matched["displayName"] == "Personal Plus"

    # Empty alias clears the value and the display name falls back to email.
    clear_response = await async_client.put(
        f"/api/accounts/{expected_account_id}/alias",
        json={"alias": "   "},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["alias"] is None
    listing = await async_client.get("/api/accounts")
    matched = next(a for a in listing.json()["accounts"] if a["accountId"] == expected_account_id)
    assert matched["alias"] is None
    assert matched["displayName"] == email
