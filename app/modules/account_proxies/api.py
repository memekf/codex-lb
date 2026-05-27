from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request

from app.core.auth.dependencies import set_dashboard_error_format, validate_dashboard_session
from app.core.exceptions import DashboardBadRequestError, DashboardConflictError, DashboardNotFoundError
from app.dependencies import AccountProxiesContext, get_account_proxies_context, get_proxy_service_for_app
from app.modules.account_proxies.schemas import (
    AccountProxiesResponse,
    AccountProxyDeleteResponse,
    AccountProxyDraftTestRequest,
    AccountProxyResponse,
    AccountProxyTestResponse,
    AccountProxyUpsertRequest,
)
from app.modules.account_proxies.service import (
    AccountProxyData,
    AccountProxyInUseError,
    AccountProxyNotFoundError,
    AccountProxyTestData,
    AccountProxyValidationError,
)

router = APIRouter(
    prefix="/api/proxies",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


@router.get("", response_model=AccountProxiesResponse)
async def list_account_proxies(
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxiesResponse:
    proxies = await context.service.list()
    return AccountProxiesResponse(proxies=[_to_response(proxy) for proxy in proxies])


@router.post("", response_model=AccountProxyResponse)
async def create_account_proxy(
    payload: AccountProxyUpsertRequest = Body(...),
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxyResponse:
    try:
        proxy = await context.service.create(payload.display_name, payload.proxy_url)
    except AccountProxyValidationError as exc:
        raise DashboardBadRequestError(str(exc), code="invalid_proxy_url") from exc
    return _to_response(proxy)


@router.post("/test", response_model=AccountProxyTestResponse)
async def test_draft_account_proxy(
    payload: AccountProxyDraftTestRequest = Body(...),
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxyTestResponse:
    try:
        result = await context.service.test_draft(payload.proxy_url)
    except AccountProxyValidationError as exc:
        raise DashboardBadRequestError(str(exc), code="invalid_proxy_url") from exc
    return _to_test_response(result)


@router.post("/{proxy_id}/test", response_model=AccountProxyResponse)
async def test_saved_account_proxy(
    proxy_id: str,
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxyResponse:
    try:
        proxy = await context.service.test_saved(proxy_id)
    except AccountProxyNotFoundError as exc:
        raise DashboardNotFoundError("Proxy not found", code="proxy_not_found") from exc
    return _to_response(proxy)


@router.put("/{proxy_id}", response_model=AccountProxyResponse)
async def update_account_proxy(
    request: Request,
    proxy_id: str,
    payload: AccountProxyUpsertRequest = Body(...),
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxyResponse:
    try:
        proxy = await context.service.update(proxy_id, payload.display_name, payload.proxy_url)
    except AccountProxyNotFoundError as exc:
        raise DashboardNotFoundError("Proxy not found", code="proxy_not_found") from exc
    except AccountProxyValidationError as exc:
        raise DashboardBadRequestError(str(exc), code="invalid_proxy_url") from exc
    if proxy.proxy_url_changed:
        await get_proxy_service_for_app(request.app).close_http_bridge_sessions_for_proxy(proxy_id)
    return _to_response(proxy)


@router.delete("/{proxy_id}", response_model=AccountProxyDeleteResponse)
async def delete_account_proxy(
    proxy_id: str,
    context: AccountProxiesContext = Depends(get_account_proxies_context),
) -> AccountProxyDeleteResponse:
    try:
        deleted = await context.service.delete(proxy_id)
    except AccountProxyInUseError as exc:
        raise DashboardConflictError(str(exc), code="proxy_in_use") from exc
    if not deleted:
        raise DashboardNotFoundError("Proxy not found", code="proxy_not_found")
    return AccountProxyDeleteResponse(status="deleted")


def _to_response(proxy: AccountProxyData) -> AccountProxyResponse:
    return AccountProxyResponse(
        id=proxy.id,
        display_name=proxy.display_name,
        redacted_proxy_url=proxy.redacted_proxy_url,
        status=proxy.status,
        last_tested_at=proxy.last_tested_at,
        last_test_error=proxy.last_test_error,
        last_test_latency_ms=proxy.last_test_latency_ms,
        created_at=proxy.created_at,
        updated_at=proxy.updated_at,
    )


def _to_test_response(result: AccountProxyTestData) -> AccountProxyTestResponse:
    return AccountProxyTestResponse(
        status=result.status,
        last_tested_at=result.last_tested_at,
        last_test_error=result.last_test_error,
        last_test_latency_ms=result.last_test_latency_ms,
    )
