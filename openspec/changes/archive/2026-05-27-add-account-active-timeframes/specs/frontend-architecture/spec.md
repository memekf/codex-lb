## ADDED Requirements

### Requirement: Dashboard exposes a Timeframes tab

The dashboard SHALL include a Timeframes tab or section that lists managed active timeframes with name, timezone, mode, local window, selected weekdays, resolved current-week weekdays, current state, and next change time. The tab SHALL support create, edit, and delete flows.

#### Scenario: Create fixed weekday timeframe from Timeframes tab
- **WHEN** an operator creates a fixed weekday timeframe
- **THEN** the app submits display name, timezone, start/end times, mode, and weekdays to `POST /api/active-timeframes`
- **AND** refreshes the timeframe list on success

#### Scenario: Create random weekly timeframe from Timeframes tab
- **WHEN** an operator creates a random weekly timeframe
- **THEN** the app submits display name, timezone, start/end times, mode, and random days per week
- **AND** displays resolved current-week weekdays after save

#### Scenario: Delete assigned timeframe surfaces conflict
- **WHEN** an operator deletes a timeframe currently assigned to accounts
- **THEN** the app surfaces the backend in-use error
- **AND** keeps the timeframe visible

### Requirement: Account views expose active timeframe assignment and health

Account list/detail views SHALL show active timeframe assignment and current schedule state beside existing account health signals. Account detail SHALL include an active timeframe dropdown that can save or clear assignment.

#### Scenario: Account detail saves active timeframe assignment
- **WHEN** an operator selects an active timeframe in account detail
- **THEN** the app calls `PUT /api/accounts/{account_id}/active-timeframe` with the selected timeframe id
- **AND** refreshes account data

#### Scenario: Account detail clears active timeframe assignment
- **WHEN** an operator selects `Always active` in account detail
- **THEN** the app calls `PUT /api/accounts/{account_id}/active-timeframe` with null
- **AND** refreshes account data

#### Scenario: Account list shows inactive timeframe problem
- **WHEN** an otherwise usable account is outside its active timeframe
- **THEN** account list/detail views show the timeframe name or reason, next change time when available, and an action-needed or unavailable routing status
