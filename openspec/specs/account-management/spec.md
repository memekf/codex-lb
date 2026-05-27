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
