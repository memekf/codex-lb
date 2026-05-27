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
