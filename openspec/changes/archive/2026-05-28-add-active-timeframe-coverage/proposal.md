# Add Active Timeframe Coverage Timetable

## Summary

Add a weekly coverage projection for account active timeframes. The backend will produce authoritative coverage segments for the selected week, and the frontend Timeframes page will render those segments as day timeline bars with summary metrics.

## Motivation

Operators can configure active timeframes, but cannot currently see whether the combined account schedule leaves coverage gaps or thin coverage periods. A weekly timetable makes the aggregate schedule visible without mixing in runtime health, quota, or proxy state.

## Scope

- Add backend schedule interval projection based on existing active-timeframe semantics.
- Add `/api/active-timeframes/coverage` for weekly coverage segments and summary metrics.
- Add frontend types, hook, timetable, summary, and page integration.
- Exclude paused and deactivated accounts.
- Include unassigned accounts as full-week coverage by default, controlled by `includeAlwaysActive`.

## Out of Scope

- Quota, proxy, rate-limit, runtime backoff, or sticky-session health in coverage counts.
- Changelog or docs updates outside OpenSpec.
