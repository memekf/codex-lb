## Context

Active timeframes are per-account routing dependencies. They must be reusable managed records, not derived account state, and must combine with existing account status, quota, and managed proxy dependency checks. The safety property is fail-closed behavior for new routing: once an account has a timeframe assignment, new selection and new account-bound outbound calls must not use the account when the timeframe cannot be resolved or is inactive.

## Goals / Non-Goals

**Goals:**

- Store named active timeframes as managed records and assign accounts by `active_timeframe_id`.
- Support fixed weekdays and deterministic random weekly days.
- Evaluate schedule state from the timeframe timezone using Monday-start local ISO weeks.
- Expose derived timeframe availability metadata on account responses without overwriting core account status.
- Exclude otherwise usable accounts outside active timeframes from load-balancer selection.
- Reject new account-bound outbound calls when assigned timeframe state is missing, invalid, or inactive.
- Keep long-lived sessions soft across clock boundaries for v1.
- Keep UI additions localized to an Active Timeframes feature folder and small account integrations.

**Non-Goals:**

- Do not persist derived active/inactive state on account rows.
- Do not store timeframe data in `auth.json` import/export.
- Do not add manual reroll controls for random weekly schedules in v1.
- Do not build a custom timezone engine; use Python `zoneinfo`.
- Do not add timeframe fingerprints to existing long-lived session reuse/send paths in v1.

## Decisions

### Use a separate `account_active_timeframes` module

The managed timeframe domain will live under `app/modules/account_active_timeframes`. The module owns validation, CRUD, schedule evaluation, random weekly resolution, response mapping, delete conflict checks, and cache invalidation for timeframe CRUD.

### Treat timeframe state as derived account availability

Account rows keep existing status and quota fields. Timeframe dependency state is returned separately as `activeTimeframeAvailability` and `activeTimeframeAvailabilityReason`. Core account status and proxy problems remain primary account health signals; timeframe state is evaluated after those checks.

### Deterministic random weekly days

Random weekly mode resolves concrete weekdays from `timeframe.id`, an internal `random_seed`, local ISO year/week, and `random_days_per_week`. The resolved weekdays are stable for the local week and are exposed in API/UI for debuggability. The seed is internal and not exposed.

### Explicit window semantics

Weekdays are local weekdays in the timeframe timezone, with Monday as `0`. `00:00-00:00` means a full selected local day. Overnight windows are valid and selected weekdays refer to the start day, so Monday `22:00-06:00` covers Monday 22:00 through Tuesday 06:00.

### Cache safety over optimization

Account-selection cache is invalidated on timeframe create/update/delete and account assignment changes. For v1, selection bypasses the cache whenever candidate inputs include at least one timeframe assignment; this avoids stale eligibility across schedule boundaries without computing per-entry TTLs.

### Soft long-lived session behavior

New WebSocket and HTTP bridge session creation must pass timeframe eligibility through account-bound transport resolution. Existing long-lived sessions are not killed or rejected solely because a timeframe window closes after creation. Assignment changes may still invalidate sessions through existing account metadata paths, but clock-boundary closure is not a v1 requirement.

## Risks / Trade-offs

- [Selection cache staleness] -> Avoid caching derived timeframe eligibility in v1 whenever candidate inputs include timeframe assignments.
- [Timezone and DST edge cases] -> Use `zoneinfo` conversions and focused tests for common boundaries; do not implement custom timezone arithmetic.
- [Overnight ambiguity] -> Specs and tests define selected weekdays as start days.
- [Random schedule debuggability] -> API/UI exposes current resolved weekdays and next change time.
- [Large integration surface] -> Implement in narrow slices with tests for schedule evaluation, API, account metadata, selection, transport, and frontend.
