from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.utils.time import utcnow
from app.db.models import AccountActiveTimeframe, AccountActiveTimeframeMode
from app.modules.account_active_timeframes.repository import AccountActiveTimeframeRepository
from app.modules.account_active_timeframes.schedule import (
    ActiveTimeframeDefinition,
    ActiveTimeframeEvaluation,
    decode_timeframe_weekdays,
    evaluate_active_timeframe,
)
from app.modules.proxy.account_cache import get_account_selection_cache

_MINUTE_OF_DAY = 24 * 60


class AccountActiveTimeframeNotFoundError(ValueError):
    pass


class AccountActiveTimeframeInUseError(ValueError):
    pass


class AccountActiveTimeframeValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AccountActiveTimeframeData:
    id: str
    display_name: str
    timezone: str
    start_time: str
    end_time: str
    start_minute: int
    end_minute: int
    mode: str
    weekdays: list[int]
    random_days_per_week: int | None
    current_weekdays: list[int]
    availability: str
    availability_reason: str
    next_change_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AccountActiveTimeframeInput:
    display_name: str
    timezone: str
    start_minute: int
    end_minute: int
    mode: AccountActiveTimeframeMode
    weekdays: list[int] | None
    random_days_per_week: int | None


class AccountActiveTimeframeService:
    def __init__(self, repository: AccountActiveTimeframeRepository) -> None:
        self._repository = repository

    async def list(self) -> list[AccountActiveTimeframeData]:
        return [self._to_data(row) for row in await self._repository.list()]

    async def create(
        self,
        *,
        display_name: str,
        timezone: str,
        start_time: str,
        end_time: str,
        mode: str,
        weekdays: list[int] | None,
        random_days_per_week: int | None,
    ) -> AccountActiveTimeframeData:
        normalized = _validate_input(
            display_name=display_name,
            timezone=timezone,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            weekdays=weekdays,
            random_days_per_week=random_days_per_week,
        )
        row = AccountActiveTimeframe(
            display_name=normalized.display_name,
            timezone=normalized.timezone,
            start_minute=normalized.start_minute,
            end_minute=normalized.end_minute,
            mode=normalized.mode,
            weekdays=_encode_weekdays(normalized.weekdays),
            random_days_per_week=normalized.random_days_per_week,
            random_seed=str(uuid.uuid4()),
        )
        created = await self._repository.create(row)
        get_account_selection_cache().invalidate()
        return self._to_data(created)

    async def update(
        self,
        timeframe_id: str,
        *,
        display_name: str,
        timezone: str,
        start_time: str,
        end_time: str,
        mode: str,
        weekdays: list[int] | None,
        random_days_per_week: int | None,
    ) -> AccountActiveTimeframeData:
        row = await self._repository.get(timeframe_id)
        if row is None:
            raise AccountActiveTimeframeNotFoundError("Active timeframe not found")
        normalized = _validate_input(
            display_name=display_name,
            timezone=timezone,
            start_time=start_time,
            end_time=end_time,
            mode=mode,
            weekdays=weekdays,
            random_days_per_week=random_days_per_week,
        )
        row.display_name = normalized.display_name
        row.timezone = normalized.timezone
        row.start_minute = normalized.start_minute
        row.end_minute = normalized.end_minute
        row.mode = normalized.mode
        row.weekdays = _encode_weekdays(normalized.weekdays)
        row.random_days_per_week = normalized.random_days_per_week
        updated = await self._repository.update(row)
        get_account_selection_cache().invalidate()
        return self._to_data(updated)

    async def delete(self, timeframe_id: str) -> bool:
        row = await self._repository.get(timeframe_id)
        if row is None:
            return False
        assignment_count = await self._repository.count_assignments(timeframe_id)
        if assignment_count > 0:
            raise AccountActiveTimeframeInUseError(f"Active timeframe is assigned to {assignment_count} account(s)")
        await self._repository.delete(row)
        get_account_selection_cache().invalidate()
        return True

    def _to_data(self, row: AccountActiveTimeframe) -> AccountActiveTimeframeData:
        mode = row.mode.value if isinstance(row.mode, AccountActiveTimeframeMode) else str(row.mode)
        decoded_weekdays = decode_timeframe_weekdays(row.weekdays)
        definition = ActiveTimeframeDefinition(
            id=row.id,
            timezone=row.timezone,
            start_minute=row.start_minute,
            end_minute=row.end_minute,
            mode=mode,
            weekdays=decoded_weekdays.weekdays,
            weekdays_valid=decoded_weekdays.valid,
            random_days_per_week=row.random_days_per_week,
            random_seed=row.random_seed,
        )
        evaluation = evaluate_active_timeframe(definition, now=utcnow())
        return AccountActiveTimeframeData(
            id=row.id,
            display_name=row.display_name,
            timezone=row.timezone,
            start_time=_format_minute(row.start_minute),
            end_time=_format_minute(row.end_minute),
            start_minute=row.start_minute,
            end_minute=row.end_minute,
            mode=mode,
            weekdays=decoded_weekdays.weekdays,
            random_days_per_week=row.random_days_per_week,
            current_weekdays=evaluation.current_weekdays,
            availability=evaluation.availability,
            availability_reason=evaluation.reason,
            next_change_at=evaluation.next_change_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _validate_input(
    *,
    display_name: str,
    timezone: str,
    start_time: str,
    end_time: str,
    mode: str,
    weekdays: list[int] | None,
    random_days_per_week: int | None,
) -> AccountActiveTimeframeInput:
    normalized_display_name = display_name.strip()
    if not normalized_display_name:
        raise AccountActiveTimeframeValidationError("displayName must not be empty")
    normalized_timezone = timezone.strip()
    try:
        ZoneInfo(normalized_timezone)
    except ZoneInfoNotFoundError as exc:
        raise AccountActiveTimeframeValidationError("timezone must be a valid IANA timezone") from exc
    try:
        normalized_mode = AccountActiveTimeframeMode(mode)
    except ValueError as exc:
        raise AccountActiveTimeframeValidationError("mode must be fixed_weekdays or random_weekly_days") from exc

    start_minute = _parse_time(start_time)
    end_minute = _parse_time(end_time)
    normalized_weekdays = sorted(set(weekdays or []))
    if any(weekday < 0 or weekday > 6 for weekday in normalized_weekdays):
        raise AccountActiveTimeframeValidationError("weekdays must be between 0 and 6")

    if normalized_mode == AccountActiveTimeframeMode.FIXED_WEEKDAYS:
        if not normalized_weekdays:
            raise AccountActiveTimeframeValidationError("fixed_weekdays mode requires weekdays")
        if random_days_per_week is not None:
            raise AccountActiveTimeframeValidationError("fixed_weekdays mode does not accept randomDaysPerWeek")
        return AccountActiveTimeframeInput(
            display_name=normalized_display_name,
            timezone=normalized_timezone,
            start_minute=start_minute,
            end_minute=end_minute,
            mode=normalized_mode,
            weekdays=normalized_weekdays,
            random_days_per_week=None,
        )

    if normalized_weekdays:
        raise AccountActiveTimeframeValidationError("random_weekly_days mode does not accept weekdays")
    if random_days_per_week is None or not 1 <= random_days_per_week <= 7:
        raise AccountActiveTimeframeValidationError("randomDaysPerWeek must be between 1 and 7")
    return AccountActiveTimeframeInput(
        display_name=normalized_display_name,
        timezone=normalized_timezone,
        start_minute=start_minute,
        end_minute=end_minute,
        mode=normalized_mode,
        weekdays=None,
        random_days_per_week=random_days_per_week,
    )


def _parse_time(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise AccountActiveTimeframeValidationError("time values must use HH:mm format")
    hour = int(parts[0])
    minute = int(parts[1])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise AccountActiveTimeframeValidationError("time values must use HH:mm format")
    return hour * 60 + minute


def _format_minute(value: int) -> str:
    if not 0 <= value < _MINUTE_OF_DAY:
        raise AccountActiveTimeframeValidationError("minute value must be between 0 and 1439")
    hour, minute = divmod(value, 60)
    return f"{hour:02d}:{minute:02d}"


def _encode_weekdays(weekdays: list[int] | None) -> str | None:
    if weekdays is None:
        return None
    return json.dumps(weekdays, separators=(",", ":"))


def evaluation_for_missing_timeframe() -> ActiveTimeframeEvaluation:
    return ActiveTimeframeEvaluation(
        availability="missing",
        reason="timeframe_missing",
        current_weekdays=[],
        next_change_at=None,
    )
