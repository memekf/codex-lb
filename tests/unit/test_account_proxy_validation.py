from __future__ import annotations

import pytest

from app.modules.account_proxies.validation import ProxyUrlValidationError, normalize_proxy_url, redact_proxy_url


def test_normalize_proxy_url_accepts_http_proxy_with_credentials() -> None:
    assert normalize_proxy_url("HTTP://User:Pass@Example.COM:8080") == "http://User:Pass@example.com:8080"


@pytest.mark.parametrize(
    "proxy_url",
    [
        "socks5://user:pass@example.com:1080",
        "http:///missing-host",
        "https://example.com/path#fragment",
        "not a url",
    ],
)
def test_normalize_proxy_url_rejects_unsupported_or_malformed_urls(proxy_url: str) -> None:
    with pytest.raises(ProxyUrlValidationError):
        normalize_proxy_url(proxy_url)


def test_redact_proxy_url_removes_embedded_credentials() -> None:
    assert redact_proxy_url("https://user:secret@example.com:8443") == "https://***:***@example.com:8443"


def test_redact_proxy_url_preserves_urls_without_credentials() -> None:
    assert redact_proxy_url("https://example.com:8443") == "https://example.com:8443"
