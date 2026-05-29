## ADDED Requirements

### Requirement: Weekly active timeframe coverage projection

The system SHALL expose a weekly active-account coverage projection derived from existing active-timeframe schedule semantics. Coverage counts SHALL include scheduled active-timeframe availability only and SHALL NOT include quota, proxy, runtime health, sticky-session, or rate-limit state.

#### Scenario: Coverage uses schedule semantics
- **WHEN** an operator requests active timeframe coverage for a week
- **THEN** the backend computes active intervals using the same fixed weekday, random weekly weekday, full-day, overnight, timezone, and local ISO week semantics as account selection

#### Scenario: Coverage includes segment details
- **WHEN** coverage is returned
- **THEN** each segment includes `start`, `end`, `activeAccountCount`, and active account labels
- **AND** zero-coverage gaps are represented by zero-count segments

#### Scenario: Coverage excludes inactive accounts
- **WHEN** accounts are paused or deactivated
- **THEN** they are excluded from coverage counts

#### Scenario: Always-active accounts are optional
- **WHEN** `includeAlwaysActive` is true or omitted
- **THEN** accounts without active timeframe assignments count as active for the full projected week
- **WHEN** `includeAlwaysActive` is false
- **THEN** accounts without active timeframe assignments are excluded from coverage counts

#### Scenario: Coverage summary is returned
- **WHEN** coverage is returned
- **THEN** the response includes minimum coverage, uncovered minutes, peak coverage, average coverage, and the next zero-coverage gap start/end when a gap exists
