# account-management Specification

## Purpose

Define account lifecycle and API behavior for managed proxy assignment and derived proxy availability.
## Requirements
### Requirement: Accounts store optional managed proxy assignment

Accounts SHALL store an optional `proxy_id` foreign key to `account_proxies.id` and SHALL NOT store raw proxy URLs. Account import/export through `auth.json` MUST remain proxy-free, and re-importing an account MUST NOT clear an existing proxy assignment.

#### Scenario: Assign account proxy
- **WHEN** an operator sets an account proxy to an existing proxy id
- **THEN** `PUT /api/accounts/{account_id}/proxy` saves that `proxy_id`
- **AND** closes local HTTP bridge sessions for that account

#### Scenario: Clear account proxy
- **WHEN** an operator clears an account proxy assignment
- **THEN** the account `proxy_id` becomes null
- **AND** closes local HTTP bridge sessions for that account

#### Scenario: Auth import preserves proxy assignment
- **GIVEN** an account already has a proxy assignment
- **WHEN** an `auth.json` import updates that account
- **THEN** the import does not clear or replace the account's proxy assignment

### Requirement: Account responses expose proxy availability metadata

Account list and detail responses SHALL include `proxyId`, `proxyDisplayName`, `proxyRedactedUrl`, `proxyStatus`, `proxyAvailability`, `proxyAvailabilityReason`, `proxyLastTestedAt`, and `proxyLastTestError`. Proxy problems MUST NOT overwrite the account's core status.

#### Scenario: Direct account reports direct availability
- **WHEN** an account has no proxy assignment
- **THEN** account responses report `proxyAvailability: direct` and `proxyAvailabilityReason: none`

#### Scenario: Failed assigned proxy reports unavailable
- **WHEN** an account is assigned to a proxy with status `failed`
- **THEN** account responses report `proxyAvailability: unavailable`
- **AND** `proxyAvailabilityReason: proxy_failed`

#### Scenario: Untested assigned proxy reports warning
- **WHEN** an account is assigned to a proxy with status `untested`
- **THEN** account responses report `proxyAvailability: warning`
- **AND** `proxyAvailabilityReason: proxy_untested`

#### Scenario: Retesting proxy preserves previous availability
- **WHEN** an assigned proxy is being retested with status `testing`
- **THEN** a previously failed test remains `proxyAvailability: unavailable`
- **AND** a previously working or untested proxy is not made unavailable merely because the retest is in progress

### Requirement: Proxy dependency affects load-balancer eligibility

Load-balancer account selection SHALL require both normal account usability and usable proxy dependency state. Direct accounts and accounts assigned to untested proxies remain eligible; accounts assigned to failed, missing, invalid, deleted, undecryptable, or unresolved proxies are ineligible.

#### Scenario: Failed proxy excludes account from selection
- **WHEN** an otherwise active account is assigned to a failed proxy
- **THEN** the load balancer does not select that account

#### Scenario: Untested proxy remains selectable
- **WHEN** an otherwise active account is assigned to an untested proxy
- **THEN** the load balancer may select that account

#### Scenario: Previously failed proxy remains excluded during retest
- **WHEN** an otherwise active account is assigned to a `testing` proxy whose prior result was failed
- **THEN** the load balancer does not select that account until a successful test result is saved

### Requirement: Auth flows carry selected managed proxy

Add-account OAuth, device login, and re-auth flows SHALL accept selected `proxyId` values. Re-auth SHALL preselect the account's current `proxyId`, and successful re-auth SHALL persist the submitted `proxyId`, including null to clear.

#### Scenario: OAuth add-account persists proxy
- **WHEN** an add-account OAuth flow starts with a selected proxy id and completes successfully
- **THEN** the created account stores that `proxy_id`

#### Scenario: Re-auth can clear proxy
- **WHEN** a re-auth flow starts for an account with an assigned proxy and submits `proxyId: null`
- **THEN** successful re-auth clears the account proxy assignment

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

