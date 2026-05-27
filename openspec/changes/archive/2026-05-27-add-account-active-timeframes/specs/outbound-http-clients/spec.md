## ADDED Requirements

### Requirement: Load-balancer selection respects active timeframe eligibility

Load-balancer account selection SHALL require normal account usability, usable proxy dependency state, and active timeframe eligibility. Timeframe eligibility SHALL be evaluated only after core account status/quota checks and proxy dependency checks pass.

#### Scenario: Inside-window account is selectable
- **WHEN** an otherwise usable account is assigned to a timeframe whose current state is active
- **THEN** the load balancer may select that account

#### Scenario: Outside-window account is skipped
- **WHEN** an otherwise usable account is assigned to a timeframe whose current state is inactive
- **THEN** the load balancer does not select that account

#### Scenario: All otherwise usable accounts outside timeframes returns distinct error
- **WHEN** all otherwise usable candidate accounts are outside their active timeframes
- **THEN** selection fails with `account_outside_active_timeframe` or `no_active_timeframe_eligible_accounts`

#### Scenario: Inactive core-status account does not require timeframe check
- **WHEN** an account fails core status or quota eligibility before timeframe evaluation
- **THEN** timeframe state is not the primary selection failure reason for that account

#### Scenario: Selection cache is bypassed for timeframe assignments
- **WHEN** candidate selection inputs include at least one account with an active timeframe assignment
- **THEN** account-selection cache is not used for that selection result

### Requirement: Account-bound transports enforce active timeframe for new outbound calls

New account-bound upstream HTTP and WebSocket transports SHALL resolve the latest account active timeframe assignment at the final outbound transport primitive and fail closed when the assigned timeframe is missing, invalid, or currently inactive.

#### Scenario: New HTTP request outside timeframe fails closed
- **WHEN** an account-bound HTTP request is sent for an account outside its assigned active timeframe
- **THEN** the wrapper rejects the request before upstream traffic can be sent
- **AND** the error code is `account_outside_active_timeframe`

#### Scenario: Missing assigned timeframe fails closed
- **WHEN** an account-bound request is sent for an account whose assigned timeframe row is missing
- **THEN** the wrapper rejects the request before upstream traffic can be sent

#### Scenario: New WebSocket connection creation outside timeframe fails closed
- **WHEN** a new account-bound upstream WebSocket connection is created for an account outside its assigned active timeframe
- **THEN** connection creation is rejected before upstream traffic can be sent
