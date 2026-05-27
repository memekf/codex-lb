from __future__ import annotations

from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountProxy, AccountProxyStatus, AccountStatus
from app.modules.accounts.mappers import build_account_summaries


def _summary_for_proxy(proxy_id: str | None, proxy: AccountProxy | None):
    encryptor = TokenEncryptor()
    account = Account(
        id=f"account-{proxy_id or 'direct'}",
        chatgpt_account_id="upstream-account",
        email="account@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-token"),
        refresh_token_encrypted=encryptor.encrypt("refresh-token"),
        id_token_encrypted=encryptor.encrypt("id-token"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        proxy_id=proxy_id,
        limit_warmup_enabled=False,
    )
    account.proxy = proxy
    return build_account_summaries(
        accounts=[account],
        primary_usage={},
        secondary_usage={},
        encryptor=encryptor,
        include_auth=False,
    )[0]


def _proxy(
    proxy_id: str,
    *,
    status: AccountProxyStatus,
    encrypted_url: bytes | None = None,
    last_test_error: str | None = None,
) -> AccountProxy:
    return AccountProxy(
        id=proxy_id,
        display_name=proxy_id,
        proxy_url_encrypted=encrypted_url or TokenEncryptor().encrypt("https://proxy.example.com:8443"),
        status=status,
        last_tested_at=utcnow(),
        last_test_error=last_test_error,
    )


def test_account_proxy_availability_reports_direct_working_and_untested_states() -> None:
    direct = _summary_for_proxy(None, None)
    working = _summary_for_proxy("working", _proxy("working", status=AccountProxyStatus.WORKING))
    untested = _summary_for_proxy("untested", _proxy("untested", status=AccountProxyStatus.UNTESTED))

    assert (direct.proxy_availability, direct.proxy_availability_reason) == ("direct", "none")
    assert (working.proxy_availability, working.proxy_availability_reason) == ("available", "none")
    assert (untested.proxy_availability, untested.proxy_availability_reason) == ("warning", "proxy_untested")


def test_account_proxy_availability_reports_all_unusable_dependency_states() -> None:
    failed = _summary_for_proxy("failed", _proxy("failed", status=AccountProxyStatus.FAILED))
    missing = _summary_for_proxy("missing", None)
    invalid = _summary_for_proxy(
        "invalid",
        _proxy(
            "invalid",
            status=AccountProxyStatus.WORKING,
            encrypted_url=TokenEncryptor().encrypt("socks5://proxy.example.com:1080"),
        ),
    )
    undecryptable = _summary_for_proxy(
        "undecryptable",
        _proxy("undecryptable", status=AccountProxyStatus.WORKING, encrypted_url=b"not-encrypted"),
    )

    assert (failed.proxy_availability, failed.proxy_availability_reason) == ("unavailable", "proxy_failed")
    assert (missing.proxy_availability, missing.proxy_availability_reason) == ("unavailable", "proxy_missing")
    assert (invalid.proxy_availability, invalid.proxy_availability_reason) == ("unavailable", "proxy_invalid")
    assert (undecryptable.proxy_availability, undecryptable.proxy_availability_reason) == (
        "unavailable",
        "proxy_decrypt_failed",
    )


def test_account_proxy_availability_preserves_previous_result_during_retest() -> None:
    previously_failed = _summary_for_proxy(
        "testing-failed",
        _proxy("testing-failed", status=AccountProxyStatus.TESTING, last_test_error="previous failure"),
    )
    previously_working = _summary_for_proxy(
        "testing-working",
        _proxy("testing-working", status=AccountProxyStatus.TESTING),
    )

    assert (previously_failed.proxy_availability, previously_failed.proxy_availability_reason) == (
        "unavailable",
        "proxy_failed",
    )
    assert (previously_working.proxy_availability, previously_working.proxy_availability_reason) == (
        "available",
        "none",
    )
