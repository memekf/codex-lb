## 1. OpenSpec Change

- [x] 1.1 Create OpenSpec artifacts for `add-active-timeframe-coverage`.
- [x] 1.2 Add requirements for weekly active-account coverage projection.
- [x] 1.3 Add frontend requirements for timetable and summary rendering.
- [x] 1.4 Validate `openspec validate add-active-timeframe-coverage`.

## 2. Schedule Interval Projection

- [x] 2.1 Add `active_intervals_between(...)`.
- [x] 2.2 Cover fixed weekdays, random weekly days, overnight windows, full-day windows, clipping, and requested range boundaries.
- [x] 2.3 Add unit tests for interval projection.

## 3. Coverage Service And API

- [x] 3.1 Add repository loading for coverage accounts with active timeframe relationships.
- [x] 3.2 Add weekly coverage service data model and segment splitting.
- [x] 3.3 Add coverage response schemas.
- [x] 3.4 Add `GET /api/active-timeframes/coverage`.
- [x] 3.5 Add integration tests for overlap, gaps, always-active inclusion, and paused/deactivated exclusion.

## 4. Frontend Coverage UI

- [x] 4.1 Add coverage schemas, API helper, and hook.
- [x] 4.2 Add weekly coverage timetable component and tests.
- [x] 4.3 Add weekly coverage summary component and tests.
- [x] 4.4 Integrate coverage into Timeframes page with `includeAlwaysActive` toggle.
- [x] 4.5 Add or update page-level/MSW tests.

## 5. Verification And Archive

- [x] 5.1 Run focused backend tests.
- [x] 5.2 Run focused frontend tests.
- [x] 5.3 Run frontend typecheck/lint/tests.
- [x] 5.4 Run `uv run ruff check app tests`.
- [x] 5.5 Run `openspec validate add-active-timeframe-coverage` and `openspec validate --specs`.
- [x] 5.6 Sync/archive the OpenSpec change after verification.
