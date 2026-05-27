## Why

Account-bound routing currently has no first-class way to restrict accounts to operator-defined local active windows. Operators need reusable, named active timeframe records that can be assigned to accounts, shown in the dashboard, and enforced for new account selection and new account-bound outbound calls without storing derived availability on account rows.

## What Changes

- Add managed active timeframe records with fixed weekday and deterministic random weekly day modes.
- Add optional account active timeframe assignment by `activeTimeframeId`, including response metadata for current schedule state, resolved weekdays, and next state change.
- Add a pure schedule evaluator with IANA timezone support, Monday week starts, full-day `00:00-00:00` handling, overnight start-day semantics, deterministic weekly random resolution, and next-change calculation.
- Update account selection so otherwise usable accounts outside their active timeframe are unavailable for routing.
- Update account-bound outbound transport resolution so new account-bound calls fail closed when the assigned timeframe is missing, invalid, or currently inactive.
- Keep existing long-lived WebSocket and HTTP bridge sessions soft for v1: do not close or reject reuse solely because a schedule boundary passes.
- Add dashboard Timeframes management and account assignment/status controls.
- Add cache safety: invalidate account-selection cache on timeframe CRUD and assignment changes, and bypass selection caching whenever candidate inputs include timeframe assignments.

## Capabilities

### New Capabilities

- `account-active-timeframe-management`: Named timeframe CRUD, validation, schedule evaluation, deterministic random weekly resolution, and assignment safety.

### Modified Capabilities

- `account-management`: Account API and account lifecycle behavior for optional active timeframe assignment and derived timeframe metadata.
- `outbound-http-clients`: Account selection and account-bound outbound transports enforce active timeframe eligibility for new calls.
- `frontend-architecture`: Dashboard navigation, Timeframes tab, account details, and account list views expose managed timeframe controls and health.
- `sticky-session-operations`: Long-lived session behavior remains soft across active timeframe schedule boundaries.

## Impact

- Backend: new `app/modules/account_active_timeframes/*`, account schemas/services/routes, transport guard updates, and load-balancer eligibility integration.
- Database: new `account_active_timeframes` table and nullable `accounts.active_timeframe_id`.
- Frontend: new `frontend/src/features/active-timeframes/*`, Timeframes tab wiring, account timeframe controls, and account status display.
- Tests: backend migration/schedule/API/account/selection/transport/cache tests, frontend Timeframes and account integration tests, and static guardrails.
