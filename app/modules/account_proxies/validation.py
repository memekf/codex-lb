from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit

_SUPPORTED_PROXY_SCHEMES = {"http", "https"}


class ProxyUrlValidationError(ValueError):
    """Raised when a managed proxy URL cannot be safely used."""


def normalize_proxy_url(proxy_url: str) -> str:
    parsed = urlsplit(proxy_url.strip())
    _validate_parsed_proxy_url(parsed)
    hostname = parsed.hostname
    if hostname is None:
        raise ProxyUrlValidationError("Proxy URL must include a host")

    userinfo = _userinfo(parsed)
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    netloc = f"{userinfo}{host}{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path, parsed.query, ""))


def redact_proxy_url(proxy_url: str) -> str:
    parsed = urlsplit(proxy_url)
    if parsed.username is None and parsed.password is None:
        return proxy_url
    hostname = parsed.hostname
    if hostname is None:
        return proxy_url
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit((parsed.scheme.lower(), f"***:***@{host}{port}", parsed.path, parsed.query, parsed.fragment))


def _validate_parsed_proxy_url(parsed: SplitResult) -> None:
    if parsed.scheme.lower() not in _SUPPORTED_PROXY_SCHEMES:
        raise ProxyUrlValidationError("Proxy URL must use http or https")
    if parsed.hostname is None:
        raise ProxyUrlValidationError("Proxy URL must include a host")
    if parsed.fragment:
        raise ProxyUrlValidationError("Proxy URL must not include a fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ProxyUrlValidationError("Proxy URL port is invalid") from exc


def _userinfo(parsed: SplitResult) -> str:
    if parsed.username is None and parsed.password is None:
        return ""
    username = parsed.username or ""
    if parsed.password is None:
        return f"{username}@"
    return f"{username}:{parsed.password}@"
