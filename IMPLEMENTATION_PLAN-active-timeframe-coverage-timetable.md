# Active Timeframe Coverage Timetable Implementation Plan

> **For agentic workers:** Implement this as a separate OpenSpec change from the base active-timeframes feature. Follow repo conventions in `AGENTS.md`; keep specs as the source of truth and do not add behavior docs under `docs/`.

**Goal:** Add a weekly coverage timetable showing how many accounts are scheduled active across the current week, using day timeline bars plus a coverage summary.

**Architecture:** Backend generates authoritative coverage segments by reusing the active-timeframe schedule semantics. Frontend renders the returned segments as proportional day timeline bars, with higher account counts shown as healthier colors and zero-coverage periods shown as gaps.

**Scope:** Count scheduled active-timeframe availability, not quota/proxy/runtime health. Paused/deactivated accounts should be excluded. Accounts without assigned timeframes should be handled explicitly with an `includeAlwaysActive` option, defaulting to `true` unless product review decides otherwise.

---

## Task 1: Create OpenSpec Change

**Files:**
- Create: `openspec/changes/add-active-timeframe-coverage/proposal.md`
- Create: `openspec/changes/add-active-timeframe-coverage/tasks.md`
- Create: `openspec/changes/add-active-timeframe-coverage/specs/account-active-timeframe-management/spec.md`
- Create or modify as needed: `openspec/changes/add-active-timeframe-coverage/specs/frontend-architecture/spec.md`

**Steps:**

- [ ] Create OpenSpec artifacts for `add-active-timeframe-coverage`.
- [ ] Add requirements for weekly coverage projection:
  - system SHALL expose weekly active-account coverage.
  - coverage SHALL use the same schedule semantics as account selection.
  - coverage SHALL include segment start/end, active account count, and account labels.
  - coverage SHALL identify zero-coverage gaps.
  - coverage SHALL expose summary metrics.
- [ ] Add frontend requirements:
  - dashboard SHALL render day timeline bars for the selected week.
  - dashboard SHALL render a coverage summary beside or below the timetable.
  - higher active-account counts SHALL be visually healthier than lower counts.
- [ ] Validate once `openspec` is available:

```bash
openspec validate add-active-timeframe-coverage
```

---

## Task 2: Add Schedule Interval Projection

**Files:**
- Modify: `app/modules/account_active_timeframes/schedule.py`
- Test: `tests/unit/test_account_active_timeframes_schedule.py`

**Implementation:**

Add a helper that projects all active intervals overlapping a requested range:

```python
def active_intervals_between(
    definition: ActiveTimeframeDefinition,
    *,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[datetime, datetime]]:
    ...
```

Rules:
- Accept aware or naive datetimes; normalize through the existing UTC helper.
- Interpret schedule boundaries in the timeframe timezone.
- Return UTC-aware interval boundaries.
- Clip intervals to `[start_at, end_at)`.
- Preserve existing semantics:
  - fixed weekdays use `weekdays`.
  - random weekly days resolve by ISO week and timeframe-local candidate date.
  - overnight windows belong to the start day.
  - `00:00-00:00` means full local day.
  - invalid definitions return no intervals or raise `ValueError` consistently with existing schedule behavior. Prefer fail-closed behavior at service/API boundaries.

**Tests:**

- [ ] Fixed weekdays return only selected weekday windows.
- [ ] Random weekly days are deterministic for a given week.
- [ ] Overnight Sunday/Monday boundaries use the candidate start date's ISO week.
- [ ] `00:00-00:00` returns full-day intervals.
- [ ] Returned intervals are clipped to the requested week range.

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_account_active_timeframes_schedule.py
```

---

## Task 3: Add Coverage Data Model and Service Method

**Files:**
- Modify: `app/modules/account_active_timeframes/service.py`
- Modify: `app/modules/account_active_timeframes/repository.py`
- Test: `tests/integration/test_account_active_timeframes_api.py`

**Repository:**

Add a method that loads accounts relevant to coverage. It should include active-timeframe relationships and enough account display fields to label segments:

```python
async def list_accounts_for_coverage(self) -> Sequence[Account]:
    ...
```

Use existing SQLAlchemy patterns. Exclude account import/export behavior.

**Service:**

Add a method like:

```python
async def weekly_coverage(
    self,
    *,
    week_start: datetime | None = None,
    include_always_active: bool = True,
) -> AccountActiveTimeframeCoverageData:
    ...
```

Behavior:
- Normalize `week_start` to the start of the selected week.
- Set `week_end = week_start + 7 days`.
- Exclude `PAUSED` and `DEACTIVATED` accounts.
- For accounts with assigned timeframes:
  - decode timeframe weekdays using `decode_timeframe_weekdays`.
  - build `ActiveTimeframeDefinition`.
  - call `active_intervals_between(...)`.
- For accounts without assigned timeframes:
  - if `include_always_active` is true, add one full-week interval.
  - if false, exclude them.
- Ignore missing/invalid timeframe assignments from active coverage, but include a warning count if useful.
- Split all interval start/end boundaries into constant-count segments.
- Include account labels per segment using alias/display name/email fallback.

Summary metrics:
- `minimum_coverage`
- `uncovered_minutes`
- `peak_coverage`
- `average_coverage`
- `next_gap_start`
- `next_gap_end`

---

## Task 4: Add API Schemas and Route

**Files:**
- Modify: `app/modules/account_active_timeframes/schemas.py`
- Modify: `app/modules/account_active_timeframes/api.py`
- Test: `tests/integration/test_account_active_timeframes_api.py`

**Endpoint:**

```http
GET /api/active-timeframes/coverage?weekStart=2026-05-25T00:00:00Z&includeAlwaysActive=true
```

**Response shape:**

```json
{
  "weekStart": "2026-05-25T00:00:00Z",
  "weekEnd": "2026-06-01T00:00:00Z",
  "segments": [
    {
      "start": "2026-05-25T09:00:00Z",
      "end": "2026-05-25T14:00:00Z",
      "activeAccountCount": 5,
      "accounts": [
        { "accountId": "acc_1", "label": "work-a" }
      ]
    }
  ],
  "summary": {
    "minimumCoverage": 0,
    "uncoveredMinutes": 1080,
    "peakCoverage": 6,
    "averageCoverage": 3.1,
    "nextGapStart": "2026-05-26T02:00:00Z",
    "nextGapEnd": "2026-05-26T05:00:00Z"
  }
}
```

**Tests:**

- [ ] Endpoint returns fixed-weekday coverage segments.
- [ ] Overlapping accounts increment `activeAccountCount`.
- [ ] Gaps produce zero-count segments or are represented clearly enough for UI gap rendering.
- [ ] `includeAlwaysActive=false` excludes accounts without assigned timeframes.
- [ ] `includeAlwaysActive=true` counts accounts without assigned timeframes across the full week.
- [ ] Paused/deactivated accounts are excluded.

Run:

```bash
.venv/bin/python -m pytest tests/integration/test_account_active_timeframes_api.py
```

---

## Task 5: Add Frontend API Types and Hook

**Files:**
- Modify: `frontend/src/features/active-timeframes/schemas.ts`
- Modify: `frontend/src/features/active-timeframes/api.ts`
- Modify: `frontend/src/features/active-timeframes/hooks/use-active-timeframes.ts`

**Schemas:**

Add Zod schemas for:
- coverage account label
- coverage segment
- coverage summary
- coverage response

Use camelCase property names to match frontend conventions:
- `weekStart`
- `weekEnd`
- `activeAccountCount`
- `minimumCoverage`
- `uncoveredMinutes`
- `peakCoverage`
- `averageCoverage`
- `nextGapStart`
- `nextGapEnd`

**API:**

Add:

```ts
export function getActiveTimeframeCoverage(params: {
  weekStart?: string;
  includeAlwaysActive?: boolean;
}) {
  ...
}
```

**Hook:**

Add:

```ts
export function useActiveTimeframeCoverage(params: {
  weekStart?: string;
  includeAlwaysActive: boolean;
}) {
  ...
}
```

Use a stable query key that includes `weekStart` and `includeAlwaysActive`.

---

## Task 6: Build Weekly Coverage Timetable UI

**Files:**
- Create: `frontend/src/features/active-timeframes/components/weekly-coverage-timetable.tsx`
- Test: `frontend/src/features/active-timeframes/components/weekly-coverage-timetable.test.tsx`

**Component props:**

```ts
type WeeklyCoverageTimetableProps = {
  coverage: AccountActiveTimeframeCoverage;
};
```

**UI behavior:**
- Render 7 rows, one per weekday.
- Render 24-hour horizontal scale with ticks at `00`, `03`, `06`, `09`, `12`, `15`, `18`, `21`, `24`.
- Render proportional coverage blocks from segment start/end.
- Use color scale:
  - zero coverage: pale red dashed gap
  - 1 account: red
  - 2 accounts: amber
  - 3 accounts: olive
  - 4 accounts: medium green
  - 5+ accounts: strong green
- Segment tooltip/title should include:
  - day and time range
  - active account count
  - account labels
- Keep the layout horizontally scrollable on narrow screens.

**Tests:**
- [ ] Renders all weekday labels.
- [ ] Renders coverage blocks with counts.
- [ ] Applies gap styling for zero coverage.
- [ ] Applies healthier color class for higher counts.
- [ ] Includes account labels in segment title.

Run:

```bash
bun run test weekly-coverage-timetable
```

---

## Task 7: Build Coverage Summary UI

**Files:**
- Create: `frontend/src/features/active-timeframes/components/weekly-coverage-summary.tsx`
- Test: `frontend/src/features/active-timeframes/components/weekly-coverage-summary.test.tsx`

**Component props:**

```ts
type WeeklyCoverageSummaryProps = {
  summary: AccountActiveTimeframeCoverageSummary;
};
```

**Metrics:**
- Minimum coverage
- Uncovered time, formatted as hours/minutes
- Peak coverage
- Average active accounts
- Next gap, formatted as day and time range

**Layout:**
- Beside timetable on desktop.
- Below timetable on mobile.
- Keep visual style consistent with current dashboard components.

Run:

```bash
bun run test weekly-coverage-summary
```

---

## Task 8: Integrate Into Timeframes Page

**Files:**
- Modify: `frontend/src/features/active-timeframes/components/active-timeframes-page.tsx`
- Test: existing active-timeframes page tests or add page-level test if none exists.

**Behavior:**
- Fetch coverage with `useActiveTimeframeCoverage`.
- Place timetable and summary above saved timeframes.
- Add a compact toggle:
  - label: `Include always-active accounts`
  - default: enabled
- Show loading state while coverage is loading.
- Show a small error state if coverage fetch fails.
- Keep existing create/update/delete timeframe behavior unchanged.

Run:

```bash
bun run test active-timeframes
```

---

## Task 9: End-to-End Verification

Run focused backend tests:

```bash
.venv/bin/python -m pytest tests/unit/test_account_active_timeframes_schedule.py tests/integration/test_account_active_timeframes_api.py
```

Run focused frontend tests:

```bash
bun run test weekly-coverage
bun run test active-timeframes
```

Run OpenSpec validation if available:

```bash
openspec validate add-active-timeframe-coverage
openspec validate --specs
```

Manual browser check:
- Open Timeframes page.
- Verify timetable has 7 rows.
- Verify summary appears beside the timetable on desktop.
- Verify summary stacks below on mobile.
- Verify higher counts are greener.
- Verify zero coverage appears as a gap.
- Toggle `Include always-active accounts` and confirm coverage changes.

---

## Notes for Implementing Agent

- Do not implement coverage calculations in frontend if backend endpoint exists. Frontend should render authoritative backend segments.
- Do not treat quota, rate-limit, proxy status, or runtime backoff as part of this feature unless the spec is explicitly expanded.
- Do not edit `CHANGELOG.md`.
- Do not add behavior docs under `docs/`; capture requirements in OpenSpec artifacts.
- Keep the existing active-timeframes CRUD behavior intact.
