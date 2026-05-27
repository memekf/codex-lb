# Account Active Timeframes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add managed active timeframes that can be assigned to accounts so account selection and new account-bound outbound access only use accounts that are active for the current local schedule.

**Architecture:** Model active timeframes as named managed records, similar to managed account proxies. Accounts store only an optional `active_timeframe_id`; all availability is derived at request/selection time from the timeframe definition, current time, account status, and proxy dependency state. Random weekly schedules are deterministic for the current week so they are stable, debuggable, and cache-safe.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Pydantic, Python `zoneinfo`, existing load-balancer/account-selection cache, React/TypeScript, TanStack Query, Vitest, pytest.

---

## Settled Product Decisions

- Timeframes are reusable managed records and accounts assign to them by id.
- No assigned timeframe means the account is always time-eligible.
- Timeframes support two modes:
  - `fixed_weekdays`: operator selects concrete weekdays.
  - `random_weekly_days`: operator selects `N` active days per week; the system deterministically resolves the concrete days for the current week.
- Timezone belongs to the timeframe and uses IANA timezone names such as `Europe/Bucharest`.
- Week starts Monday in the timeframe timezone.
- Random weekly days are stable for a whole local ISO week.
- The deterministic random seed is internal/hidden for v1. No manual reroll UI in v1.
- `00:00-00:00` means a full selected day, not invalid.
- Overnight windows are valid. Selected weekdays refer to the day the window starts; Monday `22:00-06:00` means Monday 22:00 through Tuesday 06:00.
- Delete assigned timeframe is rejected, same as assigned proxy deletion.
- Timeframe checks run only after core account usability checks. Deactivated/paused/rate-limited accounts should not be made primarily unavailable because of timeframes.
- Outside-window accounts are not selectable and new account-bound outbound calls fail closed with a distinct reason such as `account_outside_active_timeframe`.
- Existing long-lived WebSocket/HTTP bridge sessions are not killed solely because a timeframe window closes. The gate applies to new selections and new account-bound outbound calls/session creation.
- Account-selection cache must be invalidated on timeframe CRUD and account assignment changes, and must not return stale time eligibility across schedule boundaries. Safest v1: bypass selection cache when any candidate account has an active timeframe assignment.

---

## Proposed Data Model

### New table: `account_active_timeframes`

Fields:

- `id: str` UUID primary key.
- `display_name: str` required.
- `timezone: str` required IANA timezone.
- `start_minute: int` required, `0..1439`.
- `end_minute: int` required, `0..1439`.
- `mode: str` enum: `fixed_weekdays`, `random_weekly_days`.
- `weekdays: str | list[int]` for fixed mode. Store as JSON/text list or bitmask following local DB conventions.
- `random_days_per_week: int | null` for random mode, valid `1..7`.
- `random_seed: str` internal stable seed created on row creation.
- `created_at`, `updated_at`.

### Account field

Add to `accounts`:

- `active_timeframe_id: str | null` foreign key to `account_active_timeframes.id`.

Do not store derived availability on the account row.

---

## Derived Timeframe Semantics

Create a pure schedule evaluator under a focused module, e.g. `app/modules/account_active_timeframes/schedule.py`.

Inputs:

- timeframe row
- current aware datetime, defaulting to `utcnow()`

Outputs:

- `availability`: `always`, `active`, `inactive`, `missing`, `invalid`
- `reason`: `none`, `outside_window`, `timeframe_missing`, `timeframe_invalid`
- `currentWeekdays`: concrete weekdays used for this week
- `nextChangeAt`: next ISO timestamp when active/inactive state changes

Rules:

- No assigned timeframe returns `always`.
- Fixed mode uses the stored weekday list.
- Random mode resolves concrete weekdays deterministically from `timeframe.id`, `timeframe.random_seed`, local ISO year/week, and `random_days_per_week`.
- `00:00-00:00` is active for the full selected day.
- Non-overnight windows are active when local minute is `start <= minute < end` on a selected weekday.
- Overnight windows are active when either:
  - local day is selected and `minute >= start`, or
  - previous local day is selected and `minute < end`.
- For overnight windows, selected weekday is the start day.

---

## API Plan

### Managed timeframe routes

Create `app/modules/account_active_timeframes/*`:

- `api.py`
- `service.py`
- `repository.py`
- `schemas.py`
- `schedule.py`

Routes:

- `GET /api/active-timeframes`
  - Returns timeframes with display name, mode, timezone, window, fixed weekdays, random days per week, current resolved weekdays, and current/next state metadata.
- `POST /api/active-timeframes`
  - Creates a timeframe.
- `PUT /api/active-timeframes/{timeframe_id}`
  - Updates a timeframe and invalidates account-selection cache.
- `DELETE /api/active-timeframes/{timeframe_id}`
  - Rejects with conflict if assigned to any account.

Validation:

- `displayName` non-empty after trim.
- `timezone` must load via `zoneinfo.ZoneInfo`.
- `startTime` and `endTime` must parse as `HH:mm`.
- Fixed mode requires at least one weekday.
- Random mode requires `randomDaysPerWeek` in `1..7`.
- Reject mode-specific extra/missing fields with clear validation errors.

### Account assignment route

Add:

- `PUT /api/accounts/{account_id}/active-timeframe`
  - Body: `{ activeTimeframeId: string | null }`.
  - Reject missing timeframe id.
  - Save assignment.
  - Invalidate account-selection cache.

Account import/export:

- `auth.json` import/export remains timeframe-free.
- Re-importing an account preserves existing `active_timeframe_id`.

---

## Account Response Metadata

Account list/detail responses should include:

- `activeTimeframeId`
- `activeTimeframeDisplayName`
- `activeTimeframeMode`
- `activeTimeframeTimezone`
- `activeTimeframeWindow`
- `activeTimeframeWeekdays`
- `activeTimeframeResolvedWeekdays`
- `activeTimeframeAvailability`
- `activeTimeframeAvailabilityReason`
- `activeTimeframeNextChangeAt`

These are response fields only. They are never persisted as derived state.

Primary account availability should continue to prioritize core account status and proxy health. For example, a deactivated account outside its window should still primarily appear deactivated; the timeframe section may show its schedule state as inactive.

---

## Selection And Transport Plan

### Load-balancer selection

Selection eligibility becomes:

```text
eligible =
  existing account status/quota rules pass
  AND proxy dependency rules pass
  AND timeframe dependency rules pass
```

Evaluate timeframe eligibility only for accounts that survive normal status/quota checks and proxy checks.

When all otherwise usable accounts are outside active timeframes, return a distinct error code/reason:

- `account_outside_active_timeframe`
- or aggregate selection error `no_active_timeframe_eligible_accounts`

### Final account-bound transport

The account-bound transport wrapper should reload account/timeframe state and reject new account-bound outbound calls when:

- assigned timeframe row is missing
- assigned timeframe is invalid
- current time is outside the resolved active window

Use a redacted, non-sensitive error message and a stable code such as `account_outside_active_timeframe`.

### Long-lived sessions

Softer v1 rule:

- New WebSocket/HTTP bridge session creation must pass timeframe eligibility.
- Existing long-lived sessions are not closed solely because the window closes.
- Existing session reuse/send paths should not add a timeframe fingerprint or reject solely because current time moved outside the assigned timeframe.
- Assignment changes may still close or invalidate sessions if the implementation chooses to avoid stale account metadata, but the product requirement is not to interrupt solely on clock boundary.

### Account-selection cache

Cache safety requirements:

- Invalidate on active timeframe create/update/delete.
- Invalidate on account active timeframe assignment/clear.
- For v1, bypass account-selection cache whenever selection inputs contain at least one account with `active_timeframe_id`.
- Do not cache a selection result that includes derived active-window eligibility unless the cache is capped to the next schedule boundary. This optimization can be deferred.

---

## Frontend Plan

Add `frontend/src/features/active-timeframes/*`:

- API client.
- Zod schemas/types.
- Query/mutation hooks.
- Timeframes page/components.
- Integration tests.

Dashboard behavior:

- Add a `Timeframes` tab or section beside `Proxies`.
- List managed timeframes with name, timezone, mode, window, selected weekdays, resolved current-week days, current state, and next change time.
- Create/edit flow supports:
  - fixed weekdays selection
  - random weekly days selection
  - timezone select/input
  - HH:mm start/end inputs
- Delete action surfaces assigned-timeframe conflict errors.

Account behavior:

- Account detail has an active timeframe dropdown with `Always active` plus managed timeframe options.
- Account list/detail shows active timeframe status beside existing account health.
- If an otherwise usable account is outside its timeframe, show it as action-needed/unavailable for routing.
- Re-import/export UI does not expose timeframe fields in `auth.json`.

---

## Implementation Tasks

### Task 1: OpenSpec artifacts

- [ ] Create OpenSpec change `add-account-active-timeframes`.
- [ ] Add proposal describing managed active timeframes and deterministic weekly random days.
- [ ] Add design documenting schedule semantics, selection enforcement, cache safety, and softer long-lived session behavior.
- [ ] Add delta specs for:
  - `account-management`
  - new `account-active-timeframe-management`
  - `frontend-architecture`
  - `outbound-http-clients` or the relevant selection capability
  - `sticky-session-operations` for the softer long-lived session decision
- [ ] Validate with `openspec validate --specs`.

### Task 2: Data model and migration

- [ ] Add `AccountActiveTimeframe` ORM model and enum(s).
- [ ] Add `accounts.active_timeframe_id`.
- [ ] Add Alembic migration with indexes and foreign key.
- [ ] Add migration tests for table, fields, index, and FK.

### Task 3: Schedule evaluator

- [ ] Add pure schedule evaluator for fixed weekdays.
- [ ] Add `00:00-00:00` full-day behavior.
- [ ] Add overnight start-day semantics.
- [ ] Add deterministic random weekly day resolution.
- [ ] Add next-change calculation.
- [ ] Add unit tests across timezones, week boundaries, full-day windows, overnight windows, and random mode stability.

### Task 4: Backend active timeframe module

- [ ] Add repository, service, schemas, API routes, and dependency wiring.
- [ ] Add validation for timezone, HH:mm, mode-specific fields, weekday ranges, and random days per week.
- [ ] Reject deleting assigned timeframes.
- [ ] Invalidate selection cache on create/update/delete.
- [ ] Add integration tests for CRUD, validation, delete conflict, current resolved random weekdays, and cache invalidation.

### Task 5: Account assignment and response metadata

- [ ] Add account assignment API.
- [ ] Add account request/response fields and mapper support.
- [ ] Preserve active timeframe assignment on auth import/export.
- [ ] Invalidate selection cache on assignment changes.
- [ ] Add tests for save, clear, missing timeframe rejection, response metadata, and import/export preservation.

### Task 6: Load-balancer eligibility

- [ ] Integrate timeframe eligibility after core status/quota and proxy dependency checks.
- [ ] Add selection error/reason for no time-eligible accounts.
- [ ] Bypass or prevent account-selection cache use when candidate inputs include timeframe assignments.
- [ ] Add tests proving active accounts inside windows are selectable, outside-window accounts are skipped, inactive core-status accounts do not require timeframe checks, random-weekly days affect selection deterministically, and cache does not keep stale eligibility across edits.

### Task 7: Final account-bound transport guard

- [ ] Extend account-bound transport resolution to evaluate active timeframe for new account-bound outbound calls.
- [ ] Fail closed for missing/invalid/outside-window timeframes.
- [ ] Keep existing long-lived session reuse/send behavior soft per v1 decision.
- [ ] Add tests for HTTP, retry, file/model/usage/refresh, and WebSocket connection creation paths as needed.

### Task 8: Frontend Timeframes UI

- [ ] Add Timeframes route/tab.
- [ ] Add list, create, edit, delete flows.
- [ ] Add controls for fixed weekdays and random weekly day count.
- [ ] Show current resolved weekdays and next change time.
- [ ] Add account detail dropdown and account list/detail status display.
- [ ] Add MSW handlers and integration tests.

### Task 9: Guardrails and verification

- [ ] Add or extend static guardrails so new account-bound outbound paths cannot bypass active timeframe enforcement.
- [ ] Run targeted backend tests for timeframe module, account APIs, selection, transport, migration, and import/export.
- [ ] Run frontend typecheck/lint/tests.
- [ ] Run `uv run ruff check app tests`.
- [ ] Run `openspec validate --specs`.
- [ ] Sync delta specs to main specs after implementation.
- [ ] Archive the OpenSpec change after verification.

---

## Key Risks

- **Selection cache staleness:** The most likely correctness bug. Avoid caching derived time eligibility in v1 when timeframe assignments are present.
- **Overnight weekday ambiguity:** Specs must say selected weekdays are start days.
- **Random schedule debuggability:** UI/API must expose current resolved weekdays.
- **Long-lived session semantics:** Softer behavior must be explicit so reviewers do not expect boundary-time disconnects.
- **Timezone edge cases:** DST transitions can make local times ambiguous or skipped. For v1, use standard `zoneinfo` conversion and test common boundary behavior; do not build a custom timezone engine.

