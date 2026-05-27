## 1. OpenSpec Artifacts

- [x] 1.1 Create OpenSpec change `add-account-active-timeframes`.
- [x] 1.2 Add proposal describing managed active timeframes and deterministic weekly random days.
- [x] 1.3 Add design documenting schedule semantics, selection enforcement, cache safety, and softer long-lived session behavior.
- [x] 1.4 Add delta specs for account management, active timeframe management, frontend architecture, outbound clients/selection, and sticky session operations.
- [x] 1.5 Validate with `openspec validate --specs`.

## 2. Data Model And Migration

- [x] 2.1 Add `AccountActiveTimeframe` ORM model and enum(s).
- [x] 2.2 Add `accounts.active_timeframe_id`.
- [x] 2.3 Add Alembic migration with indexes and foreign key.
- [x] 2.4 Add migration tests for table, fields, index, and FK.

## 3. Schedule Evaluator

- [x] 3.1 Add pure schedule evaluator for fixed weekdays.
- [x] 3.2 Add `00:00-00:00` full-day behavior.
- [x] 3.3 Add overnight start-day semantics.
- [x] 3.4 Add deterministic random weekly day resolution.
- [x] 3.5 Add next-change calculation.
- [x] 3.6 Add unit tests across timezones, week boundaries, full-day windows, overnight windows, and random mode stability.

## 4. Backend Active Timeframe Module

- [x] 4.1 Add repository, service, schemas, API routes, and dependency wiring.
- [x] 4.2 Add validation for timezone, `HH:mm`, mode-specific fields, weekday ranges, and random days per week.
- [x] 4.3 Reject deleting assigned timeframes.
- [x] 4.4 Invalidate selection cache on create/update/delete.
- [x] 4.5 Add integration tests for CRUD, validation, delete conflict, current resolved random weekdays, and cache invalidation.

## 5. Account Assignment And Response Metadata

- [x] 5.1 Add account assignment API.
- [x] 5.2 Add account request/response fields and mapper support.
- [x] 5.3 Preserve active timeframe assignment on auth import/export.
- [x] 5.4 Invalidate selection cache on assignment changes.
- [x] 5.5 Add tests for save, clear, missing timeframe rejection, response metadata, and import/export preservation.

## 6. Load-Balancer Eligibility

- [x] 6.1 Integrate timeframe eligibility after core status/quota and proxy dependency checks.
- [x] 6.2 Add selection error/reason for no time-eligible accounts.
- [x] 6.3 Bypass or prevent account-selection cache use when candidate inputs include timeframe assignments.
- [x] 6.4 Add tests proving active accounts inside windows are selectable, outside-window accounts are skipped, inactive core-status accounts do not require timeframe checks, random-weekly days affect selection deterministically, and cache does not keep stale eligibility across edits.

## 7. Final Account-Bound Transport Guard

- [x] 7.1 Extend account-bound transport resolution to evaluate active timeframe for new account-bound outbound calls.
- [x] 7.2 Fail closed for missing/invalid/outside-window timeframes.
- [x] 7.3 Keep existing long-lived session reuse/send behavior soft per v1 decision.
- [x] 7.4 Add tests for HTTP, retry, file/model/usage/refresh, and WebSocket connection creation paths as needed.

## 8. Frontend Timeframes UI

- [x] 8.1 Add Timeframes route/tab.
- [x] 8.2 Add list, create, edit, delete flows.
- [x] 8.3 Add controls for fixed weekdays and random weekly day count.
- [x] 8.4 Show current resolved weekdays and next change time.
- [x] 8.5 Add account detail dropdown and account list/detail status display.
- [x] 8.6 Add MSW handlers and integration tests.

## 9. Guardrails And Verification

- [x] 9.1 Add or extend static guardrails so new account-bound outbound paths cannot bypass active timeframe enforcement.
- [x] 9.2 Run targeted backend tests for timeframe module, account APIs, selection, transport, migration, and import/export.
- [x] 9.3 Run frontend typecheck/lint/tests.
- [x] 9.4 Run `uv run ruff check app tests`.
- [x] 9.5 Run `openspec validate --specs`.
- [x] 9.6 Sync delta specs to main specs after implementation.
- [x] 9.7 Archive the OpenSpec change after verification.
