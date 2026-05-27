from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AvailabilityStatus = str
AvailabilityReason = str
TimeframeMode = str

_MINUTE_OF_DAY = 24 * 60
_LOOKAHEAD_DAYS = 14


@dataclass(frozen=True)
class ActiveTimeframeDefinition:
    id: str
    timezone: str
    start_minute: int
    end_minute: int
    mode: TimeframeMode
    weekdays: list[int]
    weekdays_valid: bool = True
    random_days_per_week: int | None = None
    random_seed: str | None = None


@dataclass(frozen=True)
class ActiveTimeframeEvaluation:
    availability: AvailabilityStatus
    reason: AvailabilityReason
    current_weekdays: list[int]
    next_change_at: datetime | None


@dataclass(frozen=True, slots=True)
class DecodedTimeframeWeekdays:
    weekdays: list[int]
    valid: bool


def decode_timeframe_weekdays(raw_weekdays: str | None) -> DecodedTimeframeWeekdays:
    if raw_weekdays is None:
        return DecodedTimeframeWeekdays(weekdays=[], valid=True)
    try:
        decoded = json.loads(raw_weekdays)
    except (json.JSONDecodeError, TypeError):
        return DecodedTimeframeWeekdays(weekdays=[], valid=False)
    if not isinstance(decoded, list):
        return DecodedTimeframeWeekdays(weekdays=[], valid=False)
    if any(not isinstance(value, int) or isinstance(value, bool) for value in decoded):
        return DecodedTimeframeWeekdays(weekdays=[], valid=False)
    return DecodedTimeframeWeekdays(weekdays=sorted(set(decoded)), valid=True)


def resolve_current_weekdays(definition: ActiveTimeframeDefinition, *, now: datetime) -> list[int]:
    if definition.mode == "fixed_weekdays":
        return _normalize_weekdays(definition.weekdays)
    if definition.mode != "random_weekly_days":
        raise ValueError("unsupported active timeframe mode")

    local_now = _ensure_aware_utc(now).astimezone(ZoneInfo(definition.timezone))
    return _resolve_random_weekdays_for_local_date(definition, local_now.date())


def _resolve_random_weekdays_for_local_date(definition: ActiveTimeframeDefinition, local_date: date) -> list[int]:
    if definition.random_days_per_week is None or not 1 <= definition.random_days_per_week <= 7:
        raise ValueError("random_days_per_week must be between 1 and 7")
    iso_year, iso_week, _ = local_date.isocalendar()
    seed_material = f"{definition.id}:{definition.random_seed or ''}:{iso_year}:{iso_week}".encode()
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    return sorted(rng.sample(range(7), definition.random_days_per_week))


def evaluate_active_timeframe(
    definition: ActiveTimeframeDefinition | None,
    *,
    now: datetime,
) -> ActiveTimeframeEvaluation:
    if definition is None:
        return ActiveTimeframeEvaluation(
            availability="always",
            reason="none",
            current_weekdays=[],
            next_change_at=None,
        )

    try:
        _validate_definition(definition)
        tz = ZoneInfo(definition.timezone)
        local_now = _ensure_aware_utc(now).astimezone(tz)
        current_weekdays = resolve_current_weekdays(definition, now=now)
        active_interval = _active_interval_containing(local_now, definition)
        if active_interval is not None:
            _, end_at = active_interval
            return ActiveTimeframeEvaluation(
                availability="active",
                reason="none",
                current_weekdays=current_weekdays,
                next_change_at=end_at.astimezone(timezone.utc),
            )
        return ActiveTimeframeEvaluation(
            availability="inactive",
            reason="outside_window",
            current_weekdays=current_weekdays,
            next_change_at=_next_interval_start(local_now, definition),
        )
    except (ValueError, ZoneInfoNotFoundError):
        return ActiveTimeframeEvaluation(
            availability="invalid",
            reason="timeframe_invalid",
            current_weekdays=[],
            next_change_at=None,
        )


def _validate_definition(definition: ActiveTimeframeDefinition) -> None:
    if not definition.weekdays_valid:
        raise ValueError("weekdays storage is invalid")
    if not 0 <= definition.start_minute < _MINUTE_OF_DAY:
        raise ValueError("start_minute must be between 0 and 1439")
    if not 0 <= definition.end_minute < _MINUTE_OF_DAY:
        raise ValueError("end_minute must be between 0 and 1439")
    if definition.mode not in {"fixed_weekdays", "random_weekly_days"}:
        raise ValueError("unsupported active timeframe mode")
    if definition.mode == "fixed_weekdays" and not _normalize_weekdays(definition.weekdays):
        raise ValueError("fixed_weekdays mode requires weekdays")


def _normalize_weekdays(weekdays: list[int]) -> list[int]:
    normalized = sorted(set(weekdays))
    if any(weekday < 0 or weekday > 6 for weekday in normalized):
        raise ValueError("weekdays must be between 0 and 6")
    return normalized


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _active_interval_containing(
    local_now: datetime,
    definition: ActiveTimeframeDefinition,
) -> tuple[datetime, datetime] | None:
    for day_offset in (-1, 0):
        candidate_day = (local_now + timedelta(days=day_offset)).date()
        weekdays = _weekdays_for_candidate_start_day(definition, candidate_day)
        if candidate_day.weekday() not in weekdays:
            continue
        start_at, end_at = _interval_for_start_day(local_now, candidate_day, definition)
        if start_at <= local_now < end_at:
            return start_at, end_at
    return None


def _next_interval_start(
    local_now: datetime,
    definition: ActiveTimeframeDefinition,
) -> datetime | None:
    for day_offset in range(_LOOKAHEAD_DAYS + 1):
        candidate_day = (local_now + timedelta(days=day_offset)).date()
        weekdays = _weekdays_for_candidate_start_day(definition, candidate_day)
        if candidate_day.weekday() not in weekdays:
            continue
        start_at, end_at = _interval_for_start_day(local_now, candidate_day, definition)
        if local_now < start_at:
            return start_at.astimezone(timezone.utc)
        if definition.start_minute == definition.end_minute and start_at <= local_now < end_at:
            return end_at.astimezone(timezone.utc)
    return None


def _weekdays_for_candidate_start_day(definition: ActiveTimeframeDefinition, candidate_day: date) -> list[int]:
    if definition.mode == "fixed_weekdays":
        return _normalize_weekdays(definition.weekdays)
    if definition.mode == "random_weekly_days":
        return _resolve_random_weekdays_for_local_date(definition, candidate_day)
    raise ValueError("unsupported active timeframe mode")


def _interval_for_start_day(
    local_reference: datetime,
    start_day: object,
    definition: ActiveTimeframeDefinition,
) -> tuple[datetime, datetime]:
    start_midnight = datetime.combine(start_day, datetime.min.time(), tzinfo=local_reference.tzinfo)
    start_at = start_midnight + timedelta(minutes=definition.start_minute)
    if definition.start_minute == definition.end_minute:
        return start_midnight, start_midnight + timedelta(days=1)
    if definition.start_minute < definition.end_minute:
        return start_at, start_midnight + timedelta(minutes=definition.end_minute)
    return start_at, start_midnight + timedelta(days=1, minutes=definition.end_minute)
