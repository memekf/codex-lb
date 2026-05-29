from __future__ import annotations

import pytest

from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountActiveTimeframe, AccountActiveTimeframeMode, AccountStatus
from app.db.session import SessionLocal
from app.modules.proxy.account_cache import get_account_selection_cache

pytestmark = pytest.mark.integration


def _fixed_payload(**overrides):
    payload = {
        "displayName": "Weekday office",
        "timezone": "America/New_York",
        "startTime": "09:00",
        "endTime": "17:00",
        "mode": "fixed_weekdays",
        "weekdays": [0, 1, 2, 3, 4],
    }
    payload.update(overrides)
    return payload


def _random_payload(**overrides):
    payload = {
        "displayName": "Random three days",
        "timezone": "UTC",
        "startTime": "10:00",
        "endTime": "18:00",
        "mode": "random_weekly_days",
        "randomDaysPerWeek": 3,
    }
    payload.update(overrides)
    return payload


async def _create_account(
    account_id: str,
    *,
    active_timeframe_id: str | None = None,
    alias: str | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> None:
    encryptor = TokenEncryptor()
    async with SessionLocal() as session:
        session.add(
            Account(
                id=account_id,
                chatgpt_account_id=account_id,
                email=f"{account_id}@example.com",
                alias=alias,
                plan_type="plus",
                access_token_encrypted=encryptor.encrypt("access"),
                refresh_token_encrypted=encryptor.encrypt("refresh"),
                id_token_encrypted=encryptor.encrypt("id"),
                last_refresh=utcnow(),
                status=status,
                active_timeframe_id=active_timeframe_id,
            )
        )
        await session.commit()


async def _create_timeframe(
    timeframe_id: str,
    *,
    display_name: str,
    start_minute: int,
    end_minute: int,
    weekdays: list[int],
) -> None:
    async with SessionLocal() as session:
        session.add(
            AccountActiveTimeframe(
                id=timeframe_id,
                display_name=display_name,
                timezone="UTC",
                start_minute=start_minute,
                end_minute=end_minute,
                mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
                weekdays="[" + ",".join(str(weekday) for weekday in weekdays) + "]",
                random_seed=f"{timeframe_id}-seed",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_active_timeframe_api_crud_and_cache_invalidation(async_client):
    selection_cache = get_account_selection_cache()
    generation_before = selection_cache.generation

    created = await async_client.post("/api/active-timeframes", json=_fixed_payload(displayName="  Office hours  "))

    assert created.status_code == 200
    created_payload = created.json()
    timeframe_id = created_payload["id"]
    assert selection_cache.generation > generation_before
    assert created_payload["displayName"] == "Office hours"
    assert created_payload["timezone"] == "America/New_York"
    assert created_payload["startTime"] == "09:00"
    assert created_payload["endTime"] == "17:00"
    assert created_payload["mode"] == "fixed_weekdays"
    assert created_payload["weekdays"] == [0, 1, 2, 3, 4]
    assert created_payload["randomDaysPerWeek"] is None
    assert created_payload["currentWeekdays"] == [0, 1, 2, 3, 4]
    assert "nextChangeAt" in created_payload

    listed = await async_client.get("/api/active-timeframes")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["timeframes"]] == [timeframe_id]

    generation_before_update = selection_cache.generation
    updated = await async_client.put(
        f"/api/active-timeframes/{timeframe_id}",
        json=_random_payload(displayName="Random days", randomDaysPerWeek=2),
    )

    assert updated.status_code == 200
    assert selection_cache.generation > generation_before_update
    updated_payload = updated.json()
    assert updated_payload["displayName"] == "Random days"
    assert updated_payload["mode"] == "random_weekly_days"
    assert updated_payload["weekdays"] == []
    assert updated_payload["randomDaysPerWeek"] == 2
    assert len(updated_payload["currentWeekdays"]) == 2
    assert updated_payload["currentWeekdays"] == sorted(updated_payload["currentWeekdays"])

    generation_before_delete = selection_cache.generation
    deleted = await async_client.delete(f"/api/active-timeframes/{timeframe_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert selection_cache.generation > generation_before_delete

    final = await async_client.get("/api/active-timeframes")
    assert final.status_code == 200
    assert final.json()["timeframes"] == []


@pytest.mark.asyncio
async def test_active_timeframe_api_rejects_invalid_payloads(async_client):
    bad_timezone = await async_client.post("/api/active-timeframes", json=_fixed_payload(timezone="Not/AZone"))
    assert bad_timezone.status_code == 400
    assert bad_timezone.json()["error"]["code"] == "invalid_active_timeframe"

    no_fixed_days = await async_client.post("/api/active-timeframes", json=_fixed_payload(weekdays=[]))
    assert no_fixed_days.status_code == 400
    assert no_fixed_days.json()["error"]["code"] == "invalid_active_timeframe"

    random_missing_count = await async_client.post(
        "/api/active-timeframes",
        json=_random_payload(randomDaysPerWeek=None),
    )
    assert random_missing_count.status_code == 400
    assert random_missing_count.json()["error"]["code"] == "invalid_active_timeframe"

    random_with_weekdays = await async_client.post(
        "/api/active-timeframes",
        json=_random_payload(weekdays=[0]),
    )
    assert random_with_weekdays.status_code == 400
    assert random_with_weekdays.json()["error"]["code"] == "invalid_active_timeframe"


@pytest.mark.asyncio
async def test_active_timeframe_api_rejects_delete_when_assigned(async_client):
    created = await async_client.post("/api/active-timeframes", json=_fixed_payload())
    assert created.status_code == 200
    timeframe_id = created.json()["id"]
    await _create_account("assigned-timeframe-account", active_timeframe_id=timeframe_id)

    deleted = await async_client.delete(f"/api/active-timeframes/{timeframe_id}")

    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "active_timeframe_in_use"
    async with SessionLocal() as session:
        assert await session.get(AccountActiveTimeframe, timeframe_id) is not None


@pytest.mark.asyncio
async def test_active_timeframe_coverage_returns_overlap_segments_and_gaps(async_client):
    await _create_timeframe(
        "coverage-monday-morning",
        display_name="Monday morning",
        start_minute=9 * 60,
        end_minute=17 * 60,
        weekdays=[0],
    )
    await _create_timeframe(
        "coverage-monday-afternoon",
        display_name="Monday afternoon",
        start_minute=13 * 60,
        end_minute=18 * 60,
        weekdays=[0],
    )
    await _create_account("coverage-alpha", active_timeframe_id="coverage-monday-morning", alias="Alpha")
    await _create_account("coverage-beta", active_timeframe_id="coverage-monday-afternoon")
    await _create_account("coverage-always")
    await _create_account(
        "coverage-paused",
        active_timeframe_id="coverage-monday-morning",
        status=AccountStatus.PAUSED,
    )
    await _create_account(
        "coverage-deactivated",
        active_timeframe_id="coverage-monday-morning",
        status=AccountStatus.DEACTIVATED,
    )

    response = await async_client.get(
        "/api/active-timeframes/coverage",
        params={"weekStart": "2026-05-25T00:00:00Z", "includeAlwaysActive": "false"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["weekStart"] == "2026-05-25T00:00:00Z"
    assert payload["weekEnd"] == "2026-06-01T00:00:00Z"
    segments = payload["segments"]
    monday_segments = [segment for segment in segments if segment["start"].startswith("2026-05-25")]
    assert monday_segments[:4] == [
        {
            "start": "2026-05-25T00:00:00Z",
            "end": "2026-05-25T09:00:00Z",
            "activeAccountCount": 0,
            "accounts": [],
        },
        {
            "start": "2026-05-25T09:00:00Z",
            "end": "2026-05-25T13:00:00Z",
            "activeAccountCount": 1,
            "accounts": [{"accountId": "coverage-alpha", "label": "Alpha"}],
        },
        {
            "start": "2026-05-25T13:00:00Z",
            "end": "2026-05-25T17:00:00Z",
            "activeAccountCount": 2,
            "accounts": [
                {"accountId": "coverage-alpha", "label": "Alpha"},
                {"accountId": "coverage-beta", "label": "coverage-beta@example.com"},
            ],
        },
        {
            "start": "2026-05-25T17:00:00Z",
            "end": "2026-05-25T18:00:00Z",
            "activeAccountCount": 1,
            "accounts": [{"accountId": "coverage-beta", "label": "coverage-beta@example.com"}],
        },
    ]
    assert all("coverage-always" not in str(segment["accounts"]) for segment in segments)
    assert all("coverage-paused" not in str(segment["accounts"]) for segment in segments)
    assert all("coverage-deactivated" not in str(segment["accounts"]) for segment in segments)
    assert payload["summary"]["minimumCoverage"] == 0
    assert payload["summary"]["peakCoverage"] == 2
    assert payload["summary"]["uncoveredMinutes"] > 0
    assert payload["summary"]["nextGapStart"] == "2026-05-25T00:00:00Z"
    assert payload["summary"]["nextGapEnd"] == "2026-05-25T09:00:00Z"


@pytest.mark.asyncio
async def test_active_timeframe_coverage_includes_always_active_accounts_by_default(async_client):
    await _create_timeframe(
        "coverage-default-timeframe",
        display_name="Monday window",
        start_minute=9 * 60,
        end_minute=17 * 60,
        weekdays=[0],
    )
    await _create_account("coverage-default-scheduled", active_timeframe_id="coverage-default-timeframe")
    await _create_account("coverage-default-always", alias="Always Account")

    response = await async_client.get(
        "/api/active-timeframes/coverage",
        params={"weekStart": "2026-05-25T00:00:00Z"},
    )

    assert response.status_code == 200
    payload = response.json()
    first_segment = payload["segments"][0]
    assert first_segment["activeAccountCount"] == 1
    assert first_segment["accounts"] == [{"accountId": "coverage-default-always", "label": "Always Account"}]
    overlap = next(segment for segment in payload["segments"] if segment["start"] == "2026-05-25T09:00:00Z")
    assert overlap["activeAccountCount"] == 2
    assert {"accountId": "coverage-default-scheduled", "label": "coverage-default-scheduled@example.com"} in overlap[
        "accounts"
    ]
    assert {"accountId": "coverage-default-always", "label": "Always Account"} in overlap["accounts"]
    assert payload["summary"]["minimumCoverage"] == 1
    assert payload["summary"]["uncoveredMinutes"] == 0
    assert payload["summary"]["nextGapStart"] is None
    assert payload["summary"]["nextGapEnd"] is None
