from __future__ import annotations

from datetime import datetime, timezone

from app.modules.account_active_timeframes.schedule import (
    ActiveTimeframeDefinition,
    evaluate_active_timeframe,
    resolve_current_weekdays,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _random_weekly_definition(
    *,
    timeframe_id: str,
    seed: str,
    start_minute: int,
    end_minute: int,
) -> ActiveTimeframeDefinition:
    return ActiveTimeframeDefinition(
        id=timeframe_id,
        timezone="UTC",
        start_minute=start_minute,
        end_minute=end_minute,
        mode="random_weekly_days",
        weekdays=[],
        random_days_per_week=1,
        random_seed=seed,
    )


def _seed_for_weekly_sunday_boundary(
    *,
    timeframe_id: str,
    previous_week_includes_sunday: bool,
    current_week_includes_sunday: bool,
) -> str:
    previous_sunday = _dt("2026-05-31T12:00:00")
    current_monday = _dt("2026-06-01T12:00:00")
    for index in range(512):
        seed = f"seed-{index}"
        definition = _random_weekly_definition(
            timeframe_id=timeframe_id,
            seed=seed,
            start_minute=22 * 60,
            end_minute=6 * 60,
        )
        previous_includes = 6 in resolve_current_weekdays(definition, now=previous_sunday)
        current_includes = 6 in resolve_current_weekdays(definition, now=current_monday)
        if previous_includes == previous_week_includes_sunday and current_includes == current_week_includes_sunday:
            return seed
    raise AssertionError("could not find deterministic random seed")


def _seed_for_next_week_change(
    *,
    timeframe_id: str,
    current_weekday: int,
    next_weekday: int,
) -> str:
    current_week_date = _dt("2026-06-06T12:00:00")
    next_week_date = _dt("2026-06-08T12:00:00")
    for index in range(512):
        seed = f"seed-{index}"
        definition = _random_weekly_definition(
            timeframe_id=timeframe_id,
            seed=seed,
            start_minute=9 * 60,
            end_minute=17 * 60,
        )
        if resolve_current_weekdays(definition, now=current_week_date) != [current_weekday]:
            continue
        if resolve_current_weekdays(definition, now=next_week_date) == [next_weekday]:
            return seed
    raise AssertionError("could not find deterministic random seed")


def test_missing_timeframe_is_always_available() -> None:
    evaluation = evaluate_active_timeframe(None, now=_dt("2026-05-25T12:00:00"))

    assert evaluation.availability == "always"
    assert evaluation.reason == "none"
    assert evaluation.current_weekdays == []
    assert evaluation.next_change_at is None


def test_fixed_weekday_window_is_active_in_local_timezone() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-fixed",
        timezone="America/New_York",
        start_minute=9 * 60,
        end_minute=17 * 60,
        mode="fixed_weekdays",
        weekdays=[0],
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-05-25T14:30:00"))

    assert evaluation.availability == "active"
    assert evaluation.reason == "none"
    assert evaluation.current_weekdays == [0]
    assert evaluation.next_change_at == _dt("2026-05-25T21:00:00")


def test_fixed_weekday_window_is_inactive_outside_window_with_next_start() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-fixed",
        timezone="America/New_York",
        start_minute=9 * 60,
        end_minute=17 * 60,
        mode="fixed_weekdays",
        weekdays=[0],
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-05-25T12:00:00"))

    assert evaluation.availability == "inactive"
    assert evaluation.reason == "outside_window"
    assert evaluation.next_change_at == _dt("2026-05-25T13:00:00")


def test_full_day_window_covers_selected_day_until_next_local_midnight() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-full-day",
        timezone="UTC",
        start_minute=0,
        end_minute=0,
        mode="fixed_weekdays",
        weekdays=[2],
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-05-27T23:59:00"))

    assert evaluation.availability == "active"
    assert evaluation.reason == "none"
    assert evaluation.next_change_at == _dt("2026-05-28T00:00:00")


def test_overnight_window_uses_selected_weekday_as_start_day() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-overnight",
        timezone="UTC",
        start_minute=22 * 60,
        end_minute=6 * 60,
        mode="fixed_weekdays",
        weekdays=[0],
    )

    monday_late = evaluate_active_timeframe(definition, now=_dt("2026-05-25T23:00:00"))
    tuesday_early = evaluate_active_timeframe(definition, now=_dt("2026-05-26T05:30:00"))
    tuesday_late = evaluate_active_timeframe(definition, now=_dt("2026-05-26T22:30:00"))

    assert monday_late.availability == "active"
    assert monday_late.next_change_at == _dt("2026-05-26T06:00:00")
    assert tuesday_early.availability == "active"
    assert tuesday_early.next_change_at == _dt("2026-05-26T06:00:00")
    assert tuesday_late.availability == "inactive"
    assert tuesday_late.next_change_at == _dt("2026-06-01T22:00:00")


def test_random_weekly_days_are_deterministic_per_iso_week() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-random",
        timezone="UTC",
        start_minute=9 * 60,
        end_minute=17 * 60,
        mode="random_weekly_days",
        weekdays=[],
        random_days_per_week=3,
        random_seed="seed-a",
    )

    first = resolve_current_weekdays(definition, now=_dt("2026-05-25T12:00:00"))
    second = resolve_current_weekdays(definition, now=_dt("2026-05-27T12:00:00"))
    next_week = resolve_current_weekdays(definition, now=_dt("2026-06-01T12:00:00"))

    assert first == second
    assert len(first) == 3
    assert first == sorted(first)
    assert all(0 <= weekday <= 6 for weekday in first)
    assert next_week != first


def test_random_weekly_overnight_uses_previous_week_for_sunday_start_when_monday_pre_end() -> None:
    timeframe_id = "tf-random-overnight-prev"
    definition = _random_weekly_definition(
        timeframe_id=timeframe_id,
        seed=_seed_for_weekly_sunday_boundary(
            timeframe_id=timeframe_id,
            previous_week_includes_sunday=True,
            current_week_includes_sunday=False,
        ),
        start_minute=22 * 60,
        end_minute=6 * 60,
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-06-01T05:00:00"))

    assert evaluation.availability == "active"
    assert evaluation.next_change_at == _dt("2026-06-01T06:00:00")
    assert 6 not in evaluation.current_weekdays


def test_random_weekly_overnight_does_not_use_current_week_for_previous_sunday_start() -> None:
    timeframe_id = "tf-random-overnight-current"
    definition = _random_weekly_definition(
        timeframe_id=timeframe_id,
        seed=_seed_for_weekly_sunday_boundary(
            timeframe_id=timeframe_id,
            previous_week_includes_sunday=False,
            current_week_includes_sunday=True,
        ),
        start_minute=22 * 60,
        end_minute=6 * 60,
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-06-01T05:00:00"))

    assert evaluation.availability == "inactive"
    assert evaluation.next_change_at == _dt("2026-06-07T22:00:00")
    assert 6 in evaluation.current_weekdays


def test_random_weekly_next_change_uses_following_week_resolved_day_after_final_current_day() -> None:
    timeframe_id = "tf-random-next-week"
    definition = _random_weekly_definition(
        timeframe_id=timeframe_id,
        seed=_seed_for_next_week_change(
            timeframe_id=timeframe_id,
            current_weekday=4,
            next_weekday=1,
        ),
        start_minute=9 * 60,
        end_minute=17 * 60,
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-06-06T12:00:00"))

    assert evaluation.availability == "inactive"
    assert evaluation.current_weekdays == [4]
    assert evaluation.next_change_at == _dt("2026-06-09T09:00:00")


def test_invalid_timezone_fails_closed() -> None:
    definition = ActiveTimeframeDefinition(
        id="tf-invalid",
        timezone="Not/AZone",
        start_minute=0,
        end_minute=60,
        mode="fixed_weekdays",
        weekdays=[0],
    )

    evaluation = evaluate_active_timeframe(definition, now=_dt("2026-05-25T12:00:00"))

    assert evaluation.availability == "invalid"
    assert evaluation.reason == "timeframe_invalid"
    assert evaluation.next_change_at is None
