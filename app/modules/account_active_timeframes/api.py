from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.auth.dependencies import set_dashboard_error_format, validate_dashboard_session
from app.core.exceptions import DashboardBadRequestError, DashboardConflictError, DashboardNotFoundError
from app.dependencies import AccountActiveTimeframesContext, get_account_active_timeframes_context
from app.modules.account_active_timeframes.schemas import (
    AccountActiveTimeframeDeleteResponse,
    AccountActiveTimeframeResponse,
    AccountActiveTimeframesResponse,
    AccountActiveTimeframeUpsertRequest,
)
from app.modules.account_active_timeframes.service import (
    AccountActiveTimeframeData,
    AccountActiveTimeframeInUseError,
    AccountActiveTimeframeNotFoundError,
    AccountActiveTimeframeValidationError,
)

router = APIRouter(
    prefix="/api/active-timeframes",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


@router.get("", response_model=AccountActiveTimeframesResponse)
async def list_account_active_timeframes(
    context: AccountActiveTimeframesContext = Depends(get_account_active_timeframes_context),
) -> AccountActiveTimeframesResponse:
    timeframes = await context.service.list()
    return AccountActiveTimeframesResponse(timeframes=[_to_response(timeframe) for timeframe in timeframes])


@router.post("", response_model=AccountActiveTimeframeResponse)
async def create_account_active_timeframe(
    payload: AccountActiveTimeframeUpsertRequest = Body(...),
    context: AccountActiveTimeframesContext = Depends(get_account_active_timeframes_context),
) -> AccountActiveTimeframeResponse:
    try:
        timeframe = await context.service.create(
            display_name=payload.display_name,
            timezone=payload.timezone,
            start_time=payload.start_time,
            end_time=payload.end_time,
            mode=payload.mode,
            weekdays=payload.weekdays,
            random_days_per_week=payload.random_days_per_week,
        )
    except AccountActiveTimeframeValidationError as exc:
        raise DashboardBadRequestError(str(exc), code="invalid_active_timeframe") from exc
    return _to_response(timeframe)


@router.put("/{timeframe_id}", response_model=AccountActiveTimeframeResponse)
async def update_account_active_timeframe(
    timeframe_id: str,
    payload: AccountActiveTimeframeUpsertRequest = Body(...),
    context: AccountActiveTimeframesContext = Depends(get_account_active_timeframes_context),
) -> AccountActiveTimeframeResponse:
    try:
        timeframe = await context.service.update(
            timeframe_id,
            display_name=payload.display_name,
            timezone=payload.timezone,
            start_time=payload.start_time,
            end_time=payload.end_time,
            mode=payload.mode,
            weekdays=payload.weekdays,
            random_days_per_week=payload.random_days_per_week,
        )
    except AccountActiveTimeframeNotFoundError as exc:
        raise DashboardNotFoundError("Active timeframe not found", code="active_timeframe_not_found") from exc
    except AccountActiveTimeframeValidationError as exc:
        raise DashboardBadRequestError(str(exc), code="invalid_active_timeframe") from exc
    return _to_response(timeframe)


@router.delete("/{timeframe_id}", response_model=AccountActiveTimeframeDeleteResponse)
async def delete_account_active_timeframe(
    timeframe_id: str,
    context: AccountActiveTimeframesContext = Depends(get_account_active_timeframes_context),
) -> AccountActiveTimeframeDeleteResponse:
    try:
        deleted = await context.service.delete(timeframe_id)
    except AccountActiveTimeframeInUseError as exc:
        raise DashboardConflictError(str(exc), code="active_timeframe_in_use") from exc
    if not deleted:
        raise DashboardNotFoundError("Active timeframe not found", code="active_timeframe_not_found")
    return AccountActiveTimeframeDeleteResponse(status="deleted")


def _to_response(timeframe: AccountActiveTimeframeData) -> AccountActiveTimeframeResponse:
    return AccountActiveTimeframeResponse(
        id=timeframe.id,
        display_name=timeframe.display_name,
        timezone=timeframe.timezone,
        start_time=timeframe.start_time,
        end_time=timeframe.end_time,
        start_minute=timeframe.start_minute,
        end_minute=timeframe.end_minute,
        mode=timeframe.mode,
        weekdays=timeframe.weekdays,
        random_days_per_week=timeframe.random_days_per_week,
        current_weekdays=timeframe.current_weekdays,
        availability=timeframe.availability,
        availability_reason=timeframe.availability_reason,
        next_change_at=timeframe.next_change_at,
        created_at=timeframe.created_at,
        updated_at=timeframe.updated_at,
    )
