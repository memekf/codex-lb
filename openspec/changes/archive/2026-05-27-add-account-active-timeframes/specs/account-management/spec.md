## ADDED Requirements

### Requirement: Accounts store optional active timeframe assignment

Accounts SHALL store an optional `active_timeframe_id` foreign key to `account_active_timeframes.id` and SHALL NOT store derived active/inactive state. Account import/export through `auth.json` MUST remain timeframe-free, and re-importing an account MUST NOT clear an existing active timeframe assignment.

#### Scenario: Assign account active timeframe
- **WHEN** an operator sets an account active timeframe to an existing timeframe id
- **THEN** `PUT /api/accounts/{account_id}/active-timeframe` saves that `active_timeframe_id`
- **AND** invalidates account-selection cache

#### Scenario: Clear account active timeframe
- **WHEN** an operator clears an account active timeframe assignment
- **THEN** the account `active_timeframe_id` becomes null
- **AND** invalidates account-selection cache

#### Scenario: Missing active timeframe assignment is rejected
- **WHEN** an operator assigns a non-existent active timeframe id
- **THEN** the API rejects the assignment
- **AND** the account assignment remains unchanged

#### Scenario: Auth import preserves active timeframe assignment
- **GIVEN** an account already has an active timeframe assignment
- **WHEN** an `auth.json` import updates that account
- **THEN** the import does not clear or replace the account's active timeframe assignment
- **AND** exported `auth.json` does not include active timeframe fields

### Requirement: Account responses expose active timeframe metadata

Account list and detail responses SHALL include `activeTimeframeId`, `activeTimeframeDisplayName`, `activeTimeframeMode`, `activeTimeframeTimezone`, `activeTimeframeWindow`, `activeTimeframeWeekdays`, `activeTimeframeResolvedWeekdays`, `activeTimeframeAvailability`, `activeTimeframeAvailabilityReason`, and `activeTimeframeNextChangeAt`. Timeframe problems MUST NOT overwrite the account's core status.

#### Scenario: Unassigned account reports always active
- **WHEN** an account has no active timeframe assignment
- **THEN** account responses report `activeTimeframeAvailability: always`
- **AND** `activeTimeframeAvailabilityReason: none`

#### Scenario: Assigned account reports inactive timeframe
- **WHEN** an account is assigned to a timeframe and the current local time is outside the active window
- **THEN** account responses report `activeTimeframeAvailability: inactive`
- **AND** `activeTimeframeAvailabilityReason: outside_window`

#### Scenario: Core account status remains primary
- **WHEN** a deactivated, paused, or rate-limited account is outside its active timeframe
- **THEN** the account's core status remains unchanged
- **AND** timeframe metadata may still report the schedule state separately
