## 1. OpenSpec

- [x] 1.1 Create OpenSpec change artifacts for managed account proxies.
- [x] 1.2 Validate the change with `openspec validate --specs`.

## 2. Backend Foundation

- [x] 2.1 Add database model and migration for `account_proxies`, `accounts.proxy_id`, and bridge/session proxy fingerprint persistence.
- [x] 2.2 Add proxy URL validation, normalization, redaction, encryption/decryption helpers, and tests.
- [x] 2.3 Add `app/modules/account_proxies` repository, service, schemas, API routes, and dependency wiring.
- [x] 2.4 Add draft and saved proxy test operations with persisted saved status and redacted errors.

## 3. Account Assignment And Availability

- [x] 3.1 Add account `proxyId` request/response fields and `PUT /api/accounts/{account_id}/proxy`.
- [x] 3.2 Add derived proxy availability metadata to account list/detail responses.
- [x] 3.3 Exclude accounts with unusable assigned proxies from load-balancer selection while keeping direct and untested-proxy accounts eligible.
- [x] 3.4 Preserve proxy assignment across `auth.json` import/export.

## 4. Auth Flow Integration

- [x] 4.1 Add proxy selection to OAuth/device start and flow state.
- [x] 4.2 Route pre-account OAuth/device network calls through the resolved flow proxy snapshot.
- [x] 4.3 Persist selected proxy on add-account success and changed/cleared proxy on re-auth success.

## 5. Transport Wrapper And Call Sites

- [x] 5.1 Add `app/core/clients/account_proxy.py` for account-id-based HTTP, retry, and WebSocket proxy resolution.
- [x] 5.2 Migrate account-bound one-shot HTTP/SSE call sites to the wrapper without moving endpoint-specific logic.
- [x] 5.3 Keep intentional direct paths direct.

## 6. Long-Lived Session Safety

- [x] 6.1 Add effective transport fingerprint calculation for direct and managed proxy transport.
- [x] 6.2 Store/assert fingerprints for native upstream WebSocket sessions.
- [x] 6.3 Store/assert fingerprints for HTTP bridge create/reuse/reconnect/replay/prewarm/response-create flows.
- [x] 6.4 Close local bridge sessions on account proxy assignment changes and managed proxy URL updates.

## 7. Frontend

- [x] 7.1 Add `frontend/src/features/proxies/*` API client, schemas, hooks, and Proxies tab components.
- [x] 7.2 Wire the Proxies tab into dashboard navigation.
- [x] 7.3 Add account detail proxy dropdown and account list/detail proxy health display.
- [x] 7.4 Add add-account/re-auth proxy dropdowns with current-proxy preselection.

## 8. Guardrails And Verification

- [x] 8.1 Add static bypass scan for account-bound outbound primitives outside `account_proxy` with allowlisted direct paths.
- [x] 8.2 Add backend regression tests for CRUD, validation, redaction, assignment, selection, OAuth/device, transport wrapper, and stale fingerprint behavior.
- [x] 8.3 Add frontend tests for Proxies tab, proxy testing states, account dropdown save/clear, and OAuth/re-auth dropdown behavior.
- [x] 8.4 Run targeted backend/frontend tests plus `openspec validate --specs`.
