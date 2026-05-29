# account-active-timeframe-management Specification

## Purpose
Defines reusable account active timeframe records and schedule evaluation semantics so account routing can restrict newly selected or newly accessed accounts to operator-configured local time windows.

## Requirements
### Requirement: Managed active timeframes are named reusable records

The system SHALL store account active timeframe definitions as managed `account_active_timeframes` records with `id`, `displayName`, `timezone`, `startTime`, `endTime`, `mode`, mode-specific schedule fields, internal random seed, `createdAt`, and `updatedAt`. Timezones MUST be valid IANA timezone names.

#### Scenario: Create fixed weekday timeframe
- **WHEN** an operator creates a timeframe with `mode: fixed_weekdays`, valid timezone, valid `HH:mm` start/end times, and at least one weekday
- **THEN** the API stores the timeframe
- **AND** returns the normalized timeframe without exposing the random seed

#### Scenario: Create random weekly timeframe
- **WHEN** an operator creates a timeframe with `mode: random_weekly_days`, valid timezone, valid `HH:mm` start/end times, and `randomDaysPerWeek` in `1..7`
- **THEN** the API stores the timeframe with an internal stable random seed
- **AND** returns current resolved weekdays for the local week

#### Scenario: Invalid timeframe input is rejected
- **WHEN** an operator submits an invalid timezone, malformed time, empty fixed weekdays, out-of-range weekday, invalid random day count, or mode-specific missing/extra fields
- **THEN** the API rejects the request without creating or updating a timeframe

### Requirement: Active timeframe APIs provide CRUD and current state metadata

The backend SHALL expose `/api/active-timeframes` routes for listing, creating, updating, and deleting managed timeframes. List and item responses MUST include current resolved weekdays, current availability, availability reason, and next change time.

#### Scenario: List timeframes returns current schedule state
- **WHEN** an operator lists active timeframes
- **THEN** each response includes the mode, timezone, local window, selected weekdays or random day count, resolved current-week weekdays, current state, and next change time

#### Scenario: Update timeframe invalidates selection cache
- **WHEN** an operator updates a timeframe
- **THEN** the system persists the updated definition
- **AND** invalidates account-selection cache

#### Scenario: Delete assigned timeframe is rejected
- **WHEN** an operator deletes a timeframe assigned to one or more accounts
- **THEN** the API rejects deletion with a clear in-use error
- **AND** existing account assignments remain unchanged

#### Scenario: Delete unassigned timeframe invalidates selection cache
- **WHEN** an operator deletes an unassigned timeframe
- **THEN** the timeframe is removed
- **AND** account-selection cache is invalidated

### Requirement: Schedule evaluator computes active state and next change

The system SHALL evaluate active timeframe state from an aware current datetime, the timeframe timezone, local weekdays, local start/end minutes, mode, and mode-specific fields. Evaluation SHALL return availability, reason, resolved weekdays, and next change time.

#### Scenario: No assigned timeframe is always eligible
- **WHEN** an account has no active timeframe assignment
- **THEN** schedule availability is `always`
- **AND** reason is `none`

#### Scenario: Fixed weekday window is active inside range
- **WHEN** local current time is within a selected fixed weekday window
- **THEN** schedule availability is `active`
- **AND** reason is `none`

#### Scenario: Outside fixed weekday window is inactive
- **WHEN** local current time is outside selected fixed weekday windows
- **THEN** schedule availability is `inactive`
- **AND** reason is `outside_window`

#### Scenario: Full-day window covers selected day
- **WHEN** a selected weekday uses `00:00-00:00`
- **THEN** the account is active for the entire selected local day

#### Scenario: Overnight window uses start-day semantics
- **WHEN** Monday is selected with `22:00-06:00`
- **THEN** Monday 22:00 through Tuesday 06:00 is active
- **AND** Tuesday 22:00 is inactive unless Tuesday is also selected

#### Scenario: Random weekly weekdays are stable for the local week
- **WHEN** random weekly mode is evaluated multiple times in the same local ISO week
- **THEN** the same resolved weekdays are returned
- **AND** a different local ISO week MAY resolve to a different set

#### Scenario: Missing or invalid assigned timeframe is unavailable
- **WHEN** an assigned timeframe row is missing or cannot be evaluated
- **THEN** schedule availability is `missing` or `invalid`
- **AND** the reason is `timeframe_missing` or `timeframe_invalid`

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
