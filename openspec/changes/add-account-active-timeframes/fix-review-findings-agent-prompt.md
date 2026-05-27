# Active Timeframes Review Findings Fix Prompt

Implement fixes for the active-timeframes review findings. The feature already exists in code; do not redesign it from scratch. Keep changes focused on the issues below and preserve existing behavior unless a finding explicitly requires changing it.

## Scope

Fix these files/areas as needed:

- `app/modules/account_active_timeframes/schedule.py`
- `app/modules/proxy/load_balancer.py`
- `app/core/clients/account_proxy.py`
- `app/modules/accounts/mappers.py`
- `app/modules/account_active_timeframes/service.py`
- `frontend/src/features/accounts/components/account-list-item.tsx`
- `openspec/specs/account-active-timeframe-management/spec.md`
- relevant backend/frontend tests

Do not include unrelated refactors.

## Required Fixes

### 1. Random weekly overnight week-boundary correctness

Problem: random weekly overnight windows currently resolve weekdays once for `now` and reuse that list for previous-day and future-day candidate intervals. At ISO week boundaries this can fail open or fail closed. Example: Monday 05:00 may be treated as active for a Sunday 22:00-06:00 window using the new week's resolved Sunday, even though the actual Sunday start day belongs to the previous local ISO week.

Required behavior:

- Resolve random weekly weekdays for the candidate interval start day's local ISO week.
- `_active_interval_containing` must evaluate each candidate start day using that candidate start day's resolved weekdays.
- `_next_interval_start` must evaluate each future candidate start day using that candidate start day's resolved weekdays.
- `current_weekdays` in the public evaluation response should remain the resolved weekdays for `now`'s local ISO week.
- `next_change_at` must be based on the actual next concrete interval, including intervals in a future ISO week with that future week's resolved random days.

Tests to add:

- Random weekly overnight window crossing Sunday -> Monday where previous week includes Sunday and current week does not: Monday pre-end should be active.
- Random weekly overnight window crossing Sunday -> Monday where current week includes Sunday and previous week does not: Monday pre-end should be inactive.
- `next_change_at` after the final selected random day of a week uses the next concrete interval from the following local ISO week.

### 2. Timeframe selection must run after computed core quota status

Problem: load-balancer timeframe filtering runs before usage/quota state is loaded and applied. This can make quota-exhausted accounts produce timeframe errors, even though timeframe checks should run only after core status/quota and proxy checks pass.

Required behavior:

- Keep the existing order for static account status, model support, additional limits, and proxy dependency checks where already correct.
- Load usage rows and build computed account states before applying active-timeframe eligibility.
- Apply active-timeframe filtering only to accounts whose computed state remains selectable after quota/rate-limit logic.
- If an account is quota-exhausted/rate-limited and outside or invalid timeframe, quota/rate-limit should remain the primary reason.
- Preserve the existing aggregate timeframe error codes for the case where all otherwise selectable accounts are blocked only by active timeframes.

Tests to add:

- An account that is quota-exhausted and outside its timeframe should not return `account_outside_active_timeframe`.
- An account with invalid/missing timeframe but computed quota-exhausted state should not be counted as a timeframe failure.
- Otherwise selectable accounts outside timeframes should still return the active-timeframe aggregate error.

### 3. Malformed persisted weekdays JSON must fail closed as invalid

Problem: several places call `json.loads(timeframe.weekdays)` directly. Malformed DB content can raise through account response mapping, selection, or final transport guard instead of evaluating as invalid.

Required behavior:

- Centralize timeframe weekday decoding in one shared helper, preferably near the schedule evaluator.
- The decoder must catch `json.JSONDecodeError`, `TypeError`, and invalid shapes.
- Malformed persisted weekday data must evaluate as `availability="invalid"` and `reason="timeframe_invalid"`.
- Final transport guard should fail closed with the stable public `account_outside_active_timeframe` code while preserving non-sensitive internal reason/logging if available.
- Account responses should not 500 when a timeframe row has malformed weekdays; they should surface invalid timeframe metadata.
- Selection should not 500 when a timeframe row has malformed weekdays; it should treat the account as timeframe-ineligible.

Tests to add:

- Account list/detail response with malformed `weekdays` storage returns active timeframe availability `invalid`.
- Load-balancer selection with malformed `weekdays` storage fails closed with the timeframe aggregate error when no otherwise eligible accounts remain.
- Final account-bound transport with malformed `weekdays` storage raises `AccountProxyTransportError` with code `account_outside_active_timeframe`.

### 4. Account list must show active timeframe status

Problem: account detail shows active timeframe state, but the account list row still only surfaces proxy metadata. The requirement says account list/detail should show active timeframe status.

Required behavior:

- Add a compact active-timeframe indicator to `frontend/src/features/accounts/components/account-list-item.tsx`.
- Show assigned timeframe name if present.
- Show state/reason clearly for inactive, missing, or invalid schedules.
- Keep the row compact and avoid layout shifts.
- Do not persist derived state; use existing account response fields.

Suggested display:

- No assigned timeframe: either omit the row or show `Timeframe: always` only if space is acceptable.
- Assigned and active: `Timeframe: <name> (active)`.
- Assigned and inactive: `Timeframe: <name> (inactive)`.
- Missing/invalid: surface as an issue badge or warning-colored text.

Tests to add/update:

- Account list item renders assigned active timeframe name/state.
- Inactive/missing/invalid timeframe state is visible in the list row.

### 5. Replace placeholder spec purpose

Problem: `openspec/specs/account-active-timeframe-management/spec.md` still says `Purpose TBD`.

Required behavior:

- Replace the placeholder with a concise purpose statement.
- Keep `spec.md` normative and requirement-focused.
- Do not add long narrative documentation to `spec.md`.

Suggested purpose:

```md
Defines reusable account active timeframe records and their schedule evaluation semantics so account routing can restrict newly selected or newly accessed accounts to operator-configured local time windows.
```

## Verification

Run focused verification at minimum:

```bash
uv run ruff check app tests
uv run pytest tests/unit/test_account_active_timeframes_schedule.py
uv run pytest tests/integration/test_account_active_timeframes_api.py
uv run pytest tests/integration/test_account_proxy_transport.py
uv run pytest tests/integration/test_load_balancer_integration.py
```

If frontend files are changed, also run the relevant frontend tests/typecheck available in this repo.

If `openspec` is available in PATH, run:

```bash
openspec validate --specs
```

If it is not available, report that clearly rather than pretending validation passed.

## Output Requirements

- Summarize each fixed finding.
- List files changed.
- List tests run and their results.
- Call out any verification that could not be run.
