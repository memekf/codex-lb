## Why

Account-bound upstream traffic currently has no first-class way to route specific accounts through operator-managed outbound proxies. Operators need named, testable proxy records that can be assigned to accounts without storing raw proxy URLs on account rows or allowing stale long-lived transports to keep using old direct/proxy paths.

## What Changes

- Add managed proxy records with encrypted proxy URLs, status, last test metadata, CRUD APIs, and draft/saved proxy testing.
- Add optional account proxy assignment by `proxyId`, including account response metadata for proxy health and availability.
- Update account selection so failed, missing, invalid, or undecryptable assigned proxies make affected accounts unavailable without changing the account's core status.
- Carry selected proxies through add-account OAuth, device login, and re-auth flows, then persist or clear `account.proxy_id` on success.
- Add account-bound outbound transport helpers that resolve the latest account proxy assignment at the final HTTP/WebSocket transport call and fail closed on unusable assigned proxies.
- Add transport fingerprints and invalidation so long-lived upstream sockets and HTTP bridge sessions cannot keep using stale direct/proxy transport after assignment or proxy URL changes.
- Add dashboard Proxies management and account/OAuth proxy dropdowns.
- Add guardrails that detect account-bound outbound primitives bypassing the managed transport wrapper.

## Capabilities

### New Capabilities

- `account-management`: Account API and account lifecycle behavior for optional managed proxy assignment.
- `account-proxy-management`: Named proxy CRUD, validation, testing, redaction, encrypted storage, and assignment safety.

### Modified Capabilities

- `outbound-http-clients`: Account-bound outbound calls resolve managed proxy assignment at the final transport boundary and fail closed when assigned proxies are unusable.
- `frontend-architecture`: Dashboard navigation, Proxies tab, account details, and OAuth/re-auth dialogs expose managed proxy controls and proxy health.
- `sticky-session-operations`: Long-lived account-bound sessions store and validate transport fingerprints and are invalidated when account proxy assignment or proxy URL changes.

## Impact

- Backend: new `app/modules/account_proxies/*`, account schemas/services/routes, OAuth flow state, transport client wrappers, and selected account-bound upstream call sites.
- Database: new `account_proxies` table, nullable `accounts.proxy_id`, and bridge/session proxy fingerprint persistence.
- Frontend: new `frontend/src/features/proxies/*`, Proxies tab wiring, account proxy controls, and OAuth/re-auth proxy dropdown integration.
- Tests: backend migration/API/service/transport/OAuth/selection/fingerprint tests, frontend proxy management and dropdown tests, and static bypass guardrails.
