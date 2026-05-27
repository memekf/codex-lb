## Context

Managed proxies are per-account outbound dependencies. The system must keep the current load-balancer proxy module stable while adding a separate `account_proxies` domain for operator-managed upstream egress. The critical safety property is fail-closed behavior: once an account has a proxy assignment, account-bound upstream traffic must never silently fall back to direct transport when that proxy cannot be resolved or used.

## Goals / Non-Goals

**Goals:**

- Store named proxies as encrypted managed records and assign accounts by `proxy_id`.
- Expose proxy health as derived account availability metadata without overwriting core account status.
- Resolve account proxy assignment as late as possible, at account-bound transport calls.
- Close or reject stale long-lived sessions when the effective account transport fingerprint changes.
- Keep OAuth/device pre-account flows usable by storing a resolved proxy snapshot in flow state.
- Keep UI additions localized to a Proxies feature folder and small account/OAuth integrations.

**Non-Goals:**

- Do not add `accounts.proxy_url` or keep raw proxy URLs in account import/export.
- Do not refactor endpoint-specific auth, payload construction, parsing, retry, or response handling into the transport wrapper.
- Do not proxy GitHub release checks, client-side Azure Blob uploads, internal bridge owner forwarding, health/local probes, or dashboard browser calls.
- Do not rewrite `app/modules/proxy/service.py` beyond narrow fingerprint and invalidation integration points.

## Decisions

### Use a separate `account_proxies` module

The managed proxy domain will live under `app/modules/account_proxies` to avoid confusion with the existing load-balancer `app/modules/proxy` module. The module owns validation, redaction, encrypted URL persistence, CRUD, test execution, and saved proxy status updates.

### Reject deletion while assigned

Deleting an assigned proxy will be rejected with a clear conflict response. This avoids dangling account assignments and makes cleanup explicit through account reassignment or clearing.

### Treat proxy health as derived account availability

Account rows keep their existing statuses such as `active`, `paused`, `rate_limited`, and `deactivated`. Proxy dependency state is returned separately as `proxyAvailability` and `proxyAvailabilityReason`, and load-balancer selection combines normal account usability with proxy dependency usability.

### Resolve transport at the final account-bound primitive

The `app/core/clients/account_proxy.py` wrapper accepts the local account id, reloads the latest account row, resolves and validates the current managed proxy, and applies it only to the underlying HTTP/WebSocket primitive. Existing call sites keep their endpoint-specific behavior and only swap their final network operation where practical.

### Snapshot proxies for pre-account auth flows

OAuth and device-code start endpoints accept `proxy_id`. At flow start the service resolves it to a flow-state snapshot containing `proxy_id`, normalized `proxy_url`, and a fingerprint. Pre-account network calls use that snapshot because no account row exists yet. Final account creation or re-auth persists the submitted `proxy_id`, failing closed if the referenced proxy can no longer be assigned.

### Fingerprint effective account transport

The effective transport fingerprint is `"none"` for direct traffic or a stable value containing `proxy_id` and a hash of the normalized decrypted proxy URL. Long-lived native WebSocket and HTTP bridge sessions store the connect-time fingerprint and assert that it still matches before sends, reuse, replay, prewarm, reconnect, and response creation.

## Risks / Trade-offs

- [Large migration surface] -> The plan touches auth, account selection, HTTP transports, WebSockets, bridge sessions, and frontend. Tasks should ship in narrow slices with tests at each integration point.
- [Proxy testing reliability] -> Draft/saved tests depend on external proxy reachability. Tests should stub the outbound check and verify status persistence/redaction deterministically.
- [Call-site drift] -> Static bypass scanning is needed because new account-bound outbound calls can accidentally use raw HTTP clients after the wrapper exists.
- [Long-lived continuity] -> Rejecting stale sessions can interrupt work after proxy edits, but it prevents leaking direct egress or using old proxy credentials.
