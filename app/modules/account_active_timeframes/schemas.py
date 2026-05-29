from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.shared.schemas import DashboardModel

ActiveTimeframeMode = Literal["fixed_weekdays", "random_weekly_days"]
ActiveTimeframeAvailability = Literal["always", "active", "inactive", "missing", "invalid"]
ActiveTimeframeAvailabilityReason = Literal["none", "outside_window", "timeframe_missing", "timeframe_invalid"]


class AccountActiveTimeframeResponse(DashboardModel):
    id: str
    display_name: str
    timezone: str
    start_time: str
    end_time: str
    start_minute: int
    end_minute: int
    mode: ActiveTimeframeMode
    weekdays: list[int] = Field(default_factory=list)
    random_days_per_week: int | None = None
    current_weekdays: list[int] = Field(default_factory=list)
    availability: ActiveTimeframeAvailability
    availability_reason: ActiveTimeframeAvailabilityReason
    next_change_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AccountActiveTimeframesResponse(DashboardModel):
    timeframes: list[AccountActiveTimeframeResponse] = Field(default_factory=list)


class AccountActiveTimeframeUpsertRequest(DashboardModel):
    display_name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str = Field(min_length=1)
    mode: ActiveTimeframeMode
    weekdays: list[int] | None = None
    random_days_per_week: int | None = None


class AccountActiveTimeframeDeleteResponse(DashboardModel):
    status: str


class AccountActiveTimeframeCoverageAccountResponse(DashboardModel):
    account_id: str
    label: str


class AccountActiveTimeframeCoverageSegmentResponse(DashboardModel):
    start: datetime
    end: datetime
    active_account_count: int
    accounts: list[AccountActiveTimeframeCoverageAccountResponse] = Field(default_factory=list)


class AccountActiveTimeframeCoverageSummaryResponse(DashboardModel):
    minimum_coverage: int
    uncovered_minutes: int
    peak_coverage: int
    average_coverage: float
    next_gap_start: datetime | None = None
    next_gap_end: datetime | None = None


class AccountActiveTimeframeCoverageResponse(DashboardModel):
    week_start: datetime
    week_end: datetime
    segments: list[AccountActiveTimeframeCoverageSegmentResponse] = Field(default_factory=list)
    summary: AccountActiveTimeframeCoverageSummaryResponse
