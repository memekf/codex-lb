# Active Timeframes Plan Review Prompt

Review `openspec/changes/add-account-active-timeframes/plan.md`.

Goal: critique the active timeframe feature plan before implementation. This is a design/spec review, not a code review. The feature is intended to add reusable account active timeframes, assigned to accounts, so accounts are only selectable/usable during their configured schedule.

The active-timeframes feature has not been implemented yet; only the implementation plan exists.

## Focus Areas

1. Product semantics
   - Are the rules clear for no assigned timeframe, fixed weekdays, random weekly days, `00:00-00:00`, overnight windows, and timezone handling?
   - Are weekday rules unambiguous, especially for overnight windows?
   - Is the softer behavior for long-lived sessions clear enough?

2. Data model
   - Is the proposed `account_active_timeframes` table sufficient?
   - Are fields normalized enough?
   - Are enum/mode fields and validation constraints complete?
   - Should anything else be indexed or constrained?

3. Random weekly days
   - Is deterministic weekly resolution a good design?
   - Is the seed/week calculation debuggable and stable?
   - Are there risks around timezone week boundaries, ISO week, or DST?

4. Account selection and transport enforcement
   - Does the plan correctly treat outside-window accounts like unavailable/rate-limited accounts?
   - Does it avoid checking timeframes for already deactivated/rate-limited accounts?
   - Are final transport guards sufficient to prevent bypassing selection?
   - Are cache invalidation and cache bypass rules strong enough?

5. API/frontend design
   - Are the proposed routes and response metadata enough?
   - Are account list/detail fields useful without persisting derived state?
   - Is the frontend scope complete but not overbuilt?

6. OpenSpec/test plan
   - Are the listed specs the right capabilities?
   - Are any requirements missing from the future delta specs?
   - Are the implementation tasks in the right order?
   - Are there missing test cases, especially for timezone/DST/cache/transport?

## Output Format

- Findings first, ordered by severity.
- For each finding include:
  - severity: blocker / high / medium / low
  - file/section reference
  - what is wrong or unclear
  - recommended correction
- Then list open questions.
- Then list "looks good / keep as-is" decisions.
- Do not implement code.
- Do not rewrite the whole plan unless a specific section needs replacement text.
