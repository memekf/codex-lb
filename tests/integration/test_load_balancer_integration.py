from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta, timezone

import pytest

from app.core.balancer import HEALTH_TIER_DRAINING
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
from app.modules.account_active_timeframes.schedule import ActiveTimeframeDefinition, resolve_current_weekdays
from app.modules.accounts.repository import AccountsRepository
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.proxy.account_cache import get_account_selection_cache
from app.modules.proxy.load_balancer import LoadBalancer, RuntimeState
from app.modules.proxy.repo_bundle import ProxyRepositories
from app.modules.proxy.sticky_repository import StickySessionsRepository
from app.modules.request_logs.repository import RequestLogsRepository
from app.modules.usage.repository import AdditionalUsageRepository, UsageRepository

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _repo_factory() -> AsyncIterator[ProxyRepositories]:
    async with SessionLocal() as session:
        yield ProxyRepositories(
            accounts=AccountsRepository(session),
            usage=UsageRepository(session),
            request_logs=RequestLogsRepository(session),
            sticky_sessions=StickySessionsRepository(session),
            api_keys=ApiKeysRepository(session),
            additional_usage=AdditionalUsageRepository(session),
        )


def _account(
    account_id: str,
    *,
    active_timeframe_id: str | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt(f"access-{account_id}"),
        refresh_token_encrypted=encryptor.encrypt(f"refresh-{account_id}"),
        id_token_encrypted=encryptor.encrypt(f"id-{account_id}"),
        last_refresh=utcnow(),
        status=status,
        deactivation_reason=None,
        active_timeframe_id=active_timeframe_id,
    )


def _timeframe(
    timeframe_id: str,
    *,
    weekdays: list[int],
    start_minute: int = 0,
    end_minute: int = 0,
    timezone_name: str = "UTC",
) -> AccountActiveTimeframe:
    return AccountActiveTimeframe(
        id=timeframe_id,
        display_name=timeframe_id,
        timezone=timezone_name,
        start_minute=start_minute,
        end_minute=end_minute,
        mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
        weekdays=json.dumps(weekdays),
        random_seed=f"seed-{timeframe_id}",
    )


def _malformed_timeframe(timeframe_id: str) -> AccountActiveTimeframe:
    return AccountActiveTimeframe(
        id=timeframe_id,
        display_name=timeframe_id,
        timezone="UTC",
        start_minute=0,
        end_minute=0,
        mode=AccountActiveTimeframeMode.FIXED_WEEKDAYS,
        weekdays="{not-json",
        random_seed=f"seed-{timeframe_id}",
    )


def _random_timeframe(timeframe_id: str, *, random_seed: str) -> AccountActiveTimeframe:
    return AccountActiveTimeframe(
        id=timeframe_id,
        display_name=timeframe_id,
        timezone="UTC",
        start_minute=0,
        end_minute=0,
        mode=AccountActiveTimeframeMode.RANDOM_WEEKLY_DAYS,
        weekdays=None,
        random_days_per_week=1,
        random_seed=random_seed,
    )


def _random_seed_for_current_weekday(timeframe_id: str, *, include_current: bool) -> str:
    current_weekday = utcnow().weekday()
    for index in range(128):
        seed = f"seed-{index}"
        definition = ActiveTimeframeDefinition(
            id=timeframe_id,
            timezone="UTC",
            start_minute=0,
            end_minute=0,
            mode="random_weekly_days",
            weekdays=[],
            random_days_per_week=1,
            random_seed=seed,
        )
        includes = current_weekday in resolve_current_weekdays(definition, now=utcnow())
        if includes == include_current:
            return seed
    raise AssertionError("could not find deterministic random seed")


@pytest.mark.asyncio
async def test_load_balancer_skips_accounts_outside_active_timeframes(db_setup):
    today = utcnow().weekday()
    tomorrow = (today + 1) % 7
    inside = _timeframe("tf_inside_today", weekdays=[today])
    outside = _timeframe("tf_outside_today", weekdays=[tomorrow])
    inside_account = _account("acc_timeframe_inside", active_timeframe_id=inside.id)
    outside_account = _account("acc_timeframe_outside", active_timeframe_id=outside.id)

    async with SessionLocal() as session:
        session.add_all([inside, outside, outside_account, inside_account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is not None
    assert selection.account.id == inside_account.id


@pytest.mark.asyncio
async def test_load_balancer_returns_active_timeframe_error_when_all_candidates_are_outside(db_setup):
    tomorrow = (utcnow().weekday() + 1) % 7
    timeframe = _timeframe("tf_all_outside", weekdays=[tomorrow])
    account = _account("acc_all_outside", active_timeframe_id=timeframe.id)

    async with SessionLocal() as session:
        session.add_all([timeframe, account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code == "account_outside_active_timeframe"


@pytest.mark.asyncio
async def test_load_balancer_quota_exhausted_outside_timeframe_keeps_quota_as_primary_reason(db_setup):
    del db_setup
    tomorrow = (utcnow().weekday() + 1) % 7
    timeframe = _timeframe("tf_quota_outside", weekdays=[tomorrow])
    account = _account("acc_quota_outside", active_timeframe_id=timeframe.id)
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        session.add(timeframe)
        await session.commit()
        await accounts_repo.upsert(account)
        await usage_repo.add_entry(
            account_id=account.id,
            used_percent=100.0,
            window="secondary",
            reset_at=now_epoch + 7200,
            window_minutes=10080,
            recorded_at=now,
        )

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code != "account_outside_active_timeframe"
    async with SessionLocal() as session:
        refreshed = await session.get(Account, account.id)
        assert refreshed is not None
        assert refreshed.status == AccountStatus.QUOTA_EXCEEDED


@pytest.mark.asyncio
async def test_load_balancer_quota_exhausted_invalid_timeframe_is_not_counted_as_timeframe_failure(db_setup):
    del db_setup
    tomorrow = (utcnow().weekday() + 1) % 7
    outside_timeframe = _timeframe("tf_selectable_outside", weekdays=[tomorrow])
    invalid_timeframe = _malformed_timeframe("tf_quota_malformed")
    outside_account = _account("acc_selectable_outside", active_timeframe_id=outside_timeframe.id)
    quota_account = _account("acc_quota_malformed", active_timeframe_id=invalid_timeframe.id)
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        session.add_all([outside_timeframe, invalid_timeframe])
        await session.commit()
        await accounts_repo.upsert(outside_account)
        await accounts_repo.upsert(quota_account)
        await usage_repo.add_entry(
            account_id=quota_account.id,
            used_percent=100.0,
            window="secondary",
            reset_at=now_epoch + 7200,
            window_minutes=10080,
            recorded_at=now,
        )

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code == "account_outside_active_timeframe"


@pytest.mark.asyncio
async def test_load_balancer_cooldown_account_outside_timeframe_keeps_cooldown_as_primary_reason(db_setup):
    del db_setup
    tomorrow = (utcnow().weekday() + 1) % 7
    timeframe = _timeframe("tf_cooldown_outside", weekdays=[tomorrow])
    account = _account("acc_cooldown_outside", active_timeframe_id=timeframe.id)

    async with SessionLocal() as session:
        session.add_all([timeframe, account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    balancer._runtime[account.id] = RuntimeState(cooldown_until=time.time() + 300.0)
    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code is None
    assert selection.error_message is not None
    assert "Try again in" in selection.error_message


@pytest.mark.asyncio
async def test_load_balancer_error_backoff_fallback_accounts_outside_timeframe_return_timeframe_error(db_setup):
    del db_setup
    tomorrow = (utcnow().weekday() + 1) % 7
    timeframe = _timeframe("tf_backoff_outside", weekdays=[tomorrow])
    account_a = _account("acc_backoff_outside_a", active_timeframe_id=timeframe.id)
    account_b = _account("acc_backoff_outside_b", active_timeframe_id=timeframe.id)

    async with SessionLocal() as session:
        session.add_all([timeframe, account_a, account_b])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    now = time.time()
    balancer._runtime[account_a.id] = RuntimeState(error_count=3, last_error_at=now)
    balancer._runtime[account_b.id] = RuntimeState(error_count=3, last_error_at=now)

    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code == "account_outside_active_timeframe"


@pytest.mark.asyncio
async def test_load_balancer_malformed_timeframe_weekdays_fail_closed_with_timeframe_error(db_setup):
    del db_setup
    timeframe = _malformed_timeframe("tf_malformed_selection")
    account = _account("acc_malformed_selection", active_timeframe_id=timeframe.id)

    async with SessionLocal() as session:
        session.add_all([timeframe, account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is None
    assert selection.error_code == "no_active_timeframe_eligible_accounts"


@pytest.mark.asyncio
async def test_load_balancer_does_not_check_timeframe_for_inactive_core_status_accounts(db_setup):
    invalid_timeframe = _timeframe("tf_invalid_paused", weekdays=[utcnow().weekday()], timezone_name="Not/AZone")
    paused_account = _account(
        "acc_paused_invalid_timeframe",
        active_timeframe_id=invalid_timeframe.id,
        status=AccountStatus.PAUSED,
    )
    active_account = _account("acc_active_without_timeframe")

    async with SessionLocal() as session:
        session.add_all([invalid_timeframe, paused_account, active_account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is not None
    assert selection.account.id == active_account.id


@pytest.mark.asyncio
async def test_load_balancer_applies_random_weekly_days_deterministically(db_setup):
    include = _random_timeframe(
        "tf_random_include",
        random_seed=_random_seed_for_current_weekday("tf_random_include", include_current=True),
    )
    exclude = _random_timeframe(
        "tf_random_exclude",
        random_seed=_random_seed_for_current_weekday("tf_random_exclude", include_current=False),
    )
    included_account = _account("acc_random_include", active_timeframe_id=include.id)
    excluded_account = _account("acc_random_exclude", active_timeframe_id=exclude.id)

    async with SessionLocal() as session:
        session.add_all([include, exclude, excluded_account, included_account])
        await session.commit()

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is not None
    assert selection.account.id == included_account.id


@pytest.mark.asyncio
async def test_load_balancer_bypasses_selection_cache_for_active_timeframe_assignments(db_setup):
    cache = get_account_selection_cache()
    original_ttl = cache._ttl_seconds
    cache._ttl_seconds = 60
    try:
        account = _account("acc_cache_timeframe")
        tomorrow = (utcnow().weekday() + 1) % 7
        outside = _timeframe("tf_cache_outside", weekdays=[tomorrow])
        async with SessionLocal() as session:
            session.add_all([outside, account])
            await session.commit()

        balancer = LoadBalancer(_repo_factory)
        first = await balancer.select_account()
        assert first.account is not None
        assert first.account.id == account.id

        async with SessionLocal() as session:
            stored = await session.get(Account, account.id)
            assert stored is not None
            stored.active_timeframe_id = outside.id
            await session.commit()

        second = await balancer.select_account()

        assert second.account is None
        assert second.error_code == "account_outside_active_timeframe"
    finally:
        cache._ttl_seconds = original_ttl
        cache.invalidate()


@pytest.mark.asyncio
async def test_load_balancer_skips_secondary_quota(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    primary_reset = now_epoch + 3600
    secondary_reset = now_epoch + 7200

    account_a = Account(
        id="acc_secondary_full",
        email="secondary_full@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-a"),
        refresh_token_encrypted=encryptor.encrypt("refresh-a"),
        id_token_encrypted=encryptor.encrypt("id-a"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    account_b = Account(
        id="acc_secondary_ok",
        email="secondary_ok@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-b"),
        refresh_token_encrypted=encryptor.encrypt("refresh-b"),
        id_token_encrypted=encryptor.encrypt("id-b"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(account_a)
        await accounts_repo.upsert(account_b)

        await usage_repo.add_entry(
            account_id=account_a.id,
            used_percent=10.0,
            window="primary",
            reset_at=primary_reset,
            window_minutes=300,
        )
        await usage_repo.add_entry(
            account_id=account_a.id,
            used_percent=100.0,
            window="secondary",
            reset_at=secondary_reset,
            window_minutes=10080,
        )
        await usage_repo.add_entry(
            account_id=account_b.id,
            used_percent=20.0,
            window="primary",
            reset_at=primary_reset,
            window_minutes=300,
        )
        await usage_repo.add_entry(
            account_id=account_b.id,
            used_percent=50.0,
            window="secondary",
            reset_at=secondary_reset,
            window_minutes=10080,
        )

        balancer = LoadBalancer(_repo_factory)
        selection = await balancer.select_account()

        assert selection.account is not None
        assert selection.account.id == account_b.id

        refreshed = await session.get(Account, account_a.id)
        assert refreshed is not None
        await session.refresh(refreshed)
        assert refreshed.status == AccountStatus.QUOTA_EXCEEDED


@pytest.mark.asyncio
async def test_load_balancer_reactivates_after_secondary_reset(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    primary_reset = now_epoch + 3600
    secondary_reset = now_epoch + 7200

    account = Account(
        id="acc_secondary_reset",
        email="secondary_reset@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-reset"),
        refresh_token_encrypted=encryptor.encrypt("refresh-reset"),
        id_token_encrypted=encryptor.encrypt("id-reset"),
        last_refresh=now,
        status=AccountStatus.QUOTA_EXCEEDED,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(account)

        await usage_repo.add_entry(
            account_id=account.id,
            used_percent=5.0,
            window="primary",
            reset_at=primary_reset,
            window_minutes=300,
        )
        await usage_repo.add_entry(
            account_id=account.id,
            used_percent=0.0,
            window="secondary",
            reset_at=secondary_reset,
            window_minutes=10080,
        )

        balancer = LoadBalancer(_repo_factory)
        selection = await balancer.select_account()

        assert selection.account is not None
        assert selection.account.id == account.id

        refreshed = await session.get(Account, account.id)
        assert refreshed is not None
        await session.refresh(refreshed)
        assert refreshed.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_load_balancer_treats_weekly_only_primary_as_quota_window(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    weekly_reset = now_epoch + 7200
    plus_primary_reset = now_epoch + 3600
    plus_secondary_reset = now_epoch + 7200

    free_account = Account(
        id="acc_free_weekly_full",
        email="free_weekly_full@example.com",
        plan_type="free",
        access_token_encrypted=encryptor.encrypt("free-access"),
        refresh_token_encrypted=encryptor.encrypt("free-refresh"),
        id_token_encrypted=encryptor.encrypt("free-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    plus_account = Account(
        id="acc_plus_available",
        email="plus_available@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("plus-access"),
        refresh_token_encrypted=encryptor.encrypt("plus-refresh"),
        id_token_encrypted=encryptor.encrypt("plus-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(free_account)
        await accounts_repo.upsert(plus_account)

        await usage_repo.add_entry(
            account_id=free_account.id,
            used_percent=100.0,
            window="primary",
            reset_at=weekly_reset,
            window_minutes=10080,
        )
        await usage_repo.add_entry(
            account_id=plus_account.id,
            used_percent=20.0,
            window="primary",
            reset_at=plus_primary_reset,
            window_minutes=300,
        )
        await usage_repo.add_entry(
            account_id=plus_account.id,
            used_percent=20.0,
            window="secondary",
            reset_at=plus_secondary_reset,
            window_minutes=10080,
        )

        balancer = LoadBalancer(_repo_factory)
        selection = await balancer.select_account()

        assert selection.account is not None
        assert selection.account.id == plus_account.id

        refreshed_free = await session.get(Account, free_account.id)
        assert refreshed_free is not None
        await session.refresh(refreshed_free)
        assert refreshed_free.status == AccountStatus.QUOTA_EXCEEDED


@pytest.mark.asyncio
async def test_load_balancer_excludes_failed_assigned_proxy_but_allows_untested_proxy(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    failed_proxy = AccountProxy(
        id="proxy_failed",
        display_name="Failed egress",
        proxy_url_encrypted=encryptor.encrypt("https://failed.example.com:8443"),
        status=AccountProxyStatus.FAILED,
    )
    untested_proxy = AccountProxy(
        id="proxy_untested",
        display_name="Untested egress",
        proxy_url_encrypted=encryptor.encrypt("https://untested.example.com:8443"),
        status=AccountProxyStatus.UNTESTED,
    )
    invalid_proxy = AccountProxy(
        id="proxy_invalid",
        display_name="Invalid egress",
        proxy_url_encrypted=encryptor.encrypt("socks5://invalid.example.com:1080"),
        status=AccountProxyStatus.WORKING,
    )
    undecryptable_proxy = AccountProxy(
        id="proxy_undecryptable",
        display_name="Undecryptable egress",
        proxy_url_encrypted=b"not-encrypted",
        status=AccountProxyStatus.WORKING,
    )
    failed_account = Account(
        id="acc_failed_proxy",
        email="failed-proxy@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("failed-access"),
        refresh_token_encrypted=encryptor.encrypt("failed-refresh"),
        id_token_encrypted=encryptor.encrypt("failed-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        proxy_id=failed_proxy.id,
    )
    untested_account = Account(
        id="acc_untested_proxy",
        email="untested-proxy@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("untested-access"),
        refresh_token_encrypted=encryptor.encrypt("untested-refresh"),
        id_token_encrypted=encryptor.encrypt("untested-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        proxy_id=untested_proxy.id,
    )
    invalid_account = Account(
        id="acc_invalid_proxy",
        email="invalid-proxy@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("invalid-access"),
        refresh_token_encrypted=encryptor.encrypt("invalid-refresh"),
        id_token_encrypted=encryptor.encrypt("invalid-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        proxy_id=invalid_proxy.id,
    )
    undecryptable_account = Account(
        id="acc_undecryptable_proxy",
        email="undecryptable-proxy@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("undecryptable-access"),
        refresh_token_encrypted=encryptor.encrypt("undecryptable-refresh"),
        id_token_encrypted=encryptor.encrypt("undecryptable-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        proxy_id=undecryptable_proxy.id,
    )

    async with SessionLocal() as session:
        session.add_all([failed_proxy, untested_proxy, invalid_proxy, undecryptable_proxy])
        await session.commit()
        accounts_repo = AccountsRepository(session)
        await accounts_repo.upsert(failed_account)
        await accounts_repo.upsert(untested_account)
        await accounts_repo.upsert(invalid_account)
        await accounts_repo.upsert(undecryptable_account)

        balancer = LoadBalancer(_repo_factory)
        failed_selection = await balancer.select_account(account_ids={failed_account.id})
        assert failed_selection.account is None

        untested_selection = await balancer.select_account(account_ids={untested_account.id})
        assert untested_selection.account is not None
        assert untested_selection.account.id == untested_account.id

        invalid_selection = await balancer.select_account(account_ids={invalid_account.id})
        assert invalid_selection.account is None

        undecryptable_selection = await balancer.select_account(account_ids={undecryptable_account.id})
        assert undecryptable_selection.account is None

        refreshed_failed = await session.get(Account, failed_account.id)
        assert refreshed_failed is not None
        assert refreshed_failed.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_load_balancer_preserves_proxy_eligibility_while_retest_is_in_progress(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    failed_proxy = AccountProxy(
        id="proxy_testing_failed",
        display_name="Failed under retest",
        proxy_url_encrypted=encryptor.encrypt("https://failed-retest.example.com:8443"),
        status=AccountProxyStatus.TESTING,
        last_tested_at=now,
        last_test_error="previous failure",
    )
    working_proxy = AccountProxy(
        id="proxy_testing_working",
        display_name="Working under retest",
        proxy_url_encrypted=encryptor.encrypt("https://working-retest.example.com:8443"),
        status=AccountProxyStatus.TESTING,
        last_tested_at=now,
        last_test_latency_ms=10,
    )
    failed_account = Account(
        id="acc_testing_failed",
        email="testing-failed@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("failed-access"),
        refresh_token_encrypted=encryptor.encrypt("failed-refresh"),
        id_token_encrypted=encryptor.encrypt("failed-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        proxy_id=failed_proxy.id,
    )
    working_account = Account(
        id="acc_testing_working",
        email="testing-working@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("working-access"),
        refresh_token_encrypted=encryptor.encrypt("working-refresh"),
        id_token_encrypted=encryptor.encrypt("working-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        proxy_id=working_proxy.id,
    )

    async with SessionLocal() as session:
        session.add_all([failed_proxy, working_proxy])
        await session.commit()
        accounts_repo = AccountsRepository(session)
        await accounts_repo.upsert(failed_account)
        await accounts_repo.upsert(working_account)

        balancer = LoadBalancer(_repo_factory)
        failed_selection = await balancer.select_account(account_ids={failed_account.id})
        assert failed_selection.account is None

        working_selection = await balancer.select_account(account_ids={working_account.id})
        assert working_selection.account is not None
        assert working_selection.account.id == working_account.id


@pytest.mark.asyncio
async def test_load_balancer_select_account_uses_cached_rows_for_detached_accounts(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    account = Account(
        id="acc_detached_refresh",
        email="detached-refresh@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-detached"),
        refresh_token_encrypted=encryptor.encrypt("refresh-detached"),
        id_token_encrypted=encryptor.encrypt("id-detached"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(account)
        await usage_repo.add_entry(
            account_id=account.id,
            used_percent=10.0,
            window="primary",
            reset_at=now_epoch + 300,
            window_minutes=5,
        )

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account()

    assert selection.account is not None
    assert selection.account.id == account.id
    assert selection.account.plan_type == "plus"


@pytest.mark.asyncio
async def test_load_balancer_prefers_newer_weekly_primary_over_stale_secondary(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    stale_reset = now_epoch + 1800
    weekly_reset = now_epoch + 7200
    plus_primary_reset = now_epoch + 3600
    plus_secondary_reset = now_epoch + 7200

    free_account = Account(
        id="acc_free_weekly_stale_secondary",
        email="free_weekly_stale_secondary@example.com",
        plan_type="free",
        access_token_encrypted=encryptor.encrypt("free-stale-access"),
        refresh_token_encrypted=encryptor.encrypt("free-stale-refresh"),
        id_token_encrypted=encryptor.encrypt("free-stale-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    plus_account = Account(
        id="acc_plus_weekly_control",
        email="plus_weekly_control@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("plus-control-access"),
        refresh_token_encrypted=encryptor.encrypt("plus-control-refresh"),
        id_token_encrypted=encryptor.encrypt("plus-control-id"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(free_account)
        await accounts_repo.upsert(plus_account)

        await usage_repo.add_entry(
            account_id=free_account.id,
            used_percent=15.0,
            window="secondary",
            reset_at=stale_reset,
            window_minutes=10080,
            recorded_at=now - timedelta(days=2),
        )
        await usage_repo.add_entry(
            account_id=free_account.id,
            used_percent=100.0,
            window="primary",
            reset_at=weekly_reset,
            window_minutes=10080,
            recorded_at=now,
        )
        await usage_repo.add_entry(
            account_id=plus_account.id,
            used_percent=20.0,
            window="primary",
            reset_at=plus_primary_reset,
            window_minutes=300,
        )
        await usage_repo.add_entry(
            account_id=plus_account.id,
            used_percent=20.0,
            window="secondary",
            reset_at=plus_secondary_reset,
            window_minutes=10080,
        )

        balancer = LoadBalancer(_repo_factory)
        selection = await balancer.select_account()

        assert selection.account is not None
        assert selection.account.id == plus_account.id

        refreshed_free = await session.get(Account, free_account.id)
        assert refreshed_free is not None
        await session.refresh(refreshed_free)
        assert refreshed_free.status == AccountStatus.QUOTA_EXCEEDED


@pytest.mark.asyncio
async def test_load_balancer_filters_accounts_by_persisted_additional_usage(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())

    exhausted_account = Account(
        id="acc_additional_full",
        email="additional_full@example.com",
        plan_type="pro",
        access_token_encrypted=encryptor.encrypt("access-full"),
        refresh_token_encrypted=encryptor.encrypt("refresh-full"),
        id_token_encrypted=encryptor.encrypt("id-full"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    eligible_account = Account(
        id="acc_additional_ok",
        email="additional_ok@example.com",
        plan_type="pro",
        access_token_encrypted=encryptor.encrypt("access-ok"),
        refresh_token_encrypted=encryptor.encrypt("refresh-ok"),
        id_token_encrypted=encryptor.encrypt("id-ok"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        additional_repo = AdditionalUsageRepository(session)
        await accounts_repo.upsert(exhausted_account)
        await accounts_repo.upsert(eligible_account)

        for account, used_percent in ((exhausted_account, 40.0), (eligible_account, 20.0)):
            await usage_repo.add_entry(
                account_id=account.id,
                used_percent=used_percent,
                window="primary",
                reset_at=now_epoch + 300,
                window_minutes=5,
                recorded_at=now,
            )

        await additional_repo.add_entry(
            account_id=exhausted_account.id,
            limit_name="codex_other",
            metered_feature="codex_bengalfox",
            window="primary",
            used_percent=100.0,
            reset_at=now_epoch + 300,
            window_minutes=5,
            recorded_at=now,
        )
        await additional_repo.add_entry(
            account_id=eligible_account.id,
            limit_name="codex_other",
            metered_feature="codex_bengalfox",
            window="primary",
            used_percent=25.0,
            reset_at=now_epoch + 300,
            window_minutes=5,
            recorded_at=now,
        )

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account(additional_limit_name="codex_spark")

    assert selection.account is not None
    assert selection.account.id == eligible_account.id


@pytest.mark.asyncio
async def test_load_balancer_selects_best_draining_account_when_all_are_draining(db_setup):
    encryptor = TokenEncryptor()
    now = utcnow()
    now_epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    primary_reset = now_epoch + 3600
    secondary_reset = now_epoch + 7200

    account_a = Account(
        id="acc_all_draining_a",
        email="all_draining_a@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-drain-a"),
        refresh_token_encrypted=encryptor.encrypt("refresh-drain-a"),
        id_token_encrypted=encryptor.encrypt("id-drain-a"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    account_b = Account(
        id="acc_all_draining_b",
        email="all_draining_b@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-drain-b"),
        refresh_token_encrypted=encryptor.encrypt("refresh-drain-b"),
        id_token_encrypted=encryptor.encrypt("id-drain-b"),
        last_refresh=now,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )

    async with SessionLocal() as session:
        accounts_repo = AccountsRepository(session)
        usage_repo = UsageRepository(session)
        await accounts_repo.upsert(account_a)
        await accounts_repo.upsert(account_b)

        await usage_repo.add_entry(
            account_id=account_a.id,
            used_percent=94.0,
            window="primary",
            reset_at=primary_reset,
            window_minutes=300,
            recorded_at=now,
        )
        await usage_repo.add_entry(
            account_id=account_a.id,
            used_percent=96.0,
            window="secondary",
            reset_at=secondary_reset,
            window_minutes=10080,
            recorded_at=now,
        )
        await usage_repo.add_entry(
            account_id=account_b.id,
            used_percent=88.0,
            window="primary",
            reset_at=primary_reset,
            window_minutes=300,
            recorded_at=now,
        )
        await usage_repo.add_entry(
            account_id=account_b.id,
            used_percent=93.0,
            window="secondary",
            reset_at=secondary_reset,
            window_minutes=10080,
            recorded_at=now,
        )

    balancer = LoadBalancer(_repo_factory)
    selection = await balancer.select_account(routing_strategy="usage_weighted")

    assert selection.account is not None
    assert selection.account.id == account_b.id
    assert balancer._runtime[account_a.id].health_tier == HEALTH_TIER_DRAINING
    assert balancer._runtime[account_b.id].health_tier == HEALTH_TIER_DRAINING
