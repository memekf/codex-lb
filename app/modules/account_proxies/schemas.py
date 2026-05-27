from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.shared.schemas import DashboardModel

ProxyStatus = Literal["untested", "testing", "working", "failed"]


class AccountProxyResponse(DashboardModel):
    id: str
    display_name: str
    redacted_proxy_url: str
    status: ProxyStatus
    last_tested_at: datetime | None = None
    last_test_error: str | None = None
    last_test_latency_ms: int | None = None
    created_at: datetime
    updated_at: datetime


class AccountProxiesResponse(DashboardModel):
    proxies: list[AccountProxyResponse] = Field(default_factory=list)


class AccountProxyUpsertRequest(DashboardModel):
    display_name: str = Field(min_length=1, max_length=255)
    proxy_url: str = Field(min_length=1)


class AccountProxyDraftTestRequest(DashboardModel):
    proxy_url: str = Field(min_length=1)


class AccountProxyTestResponse(DashboardModel):
    status: ProxyStatus
    last_tested_at: datetime
    last_test_error: str | None = None
    last_test_latency_ms: int | None = None


class AccountProxyDeleteResponse(DashboardModel):
    status: str
