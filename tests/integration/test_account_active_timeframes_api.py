from __future__ import annotations

import pytest

from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountActiveTimeframe
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


async def _create_account(account_id: str, *, active_timeframe_id: str | None = None) -> None:
    encryptor = TokenEncryptor()
    async with SessionLocal() as session:
        session.add(
            Account(
                id=account_id,
                chatgpt_account_id=account_id,
                email=f"{account_id}@example.com",
                plan_type="plus",
                access_token_encrypted=encryptor.encrypt("access"),
                refresh_token_encrypted=encryptor.encrypt("refresh"),
                id_token_encrypted=encryptor.encrypt("id"),
                last_refresh=utcnow(),
                active_timeframe_id=active_timeframe_id,
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
