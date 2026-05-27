## ADDED Requirements

### Requirement: Dashboard exposes a Proxies tab

The dashboard SHALL include a Proxies tab that lists managed proxies with name, redacted URL, status, last tested time, latency, and redacted error information. The tab SHALL support create, edit, delete, draft test, and saved test flows.

#### Scenario: Create proxy from Proxies tab
- **WHEN** an operator creates a proxy from the Proxies tab
- **THEN** the app submits the display name and proxy URL to `POST /api/proxies`
- **AND** refreshes the proxy list on success

#### Scenario: Test draft proxy
- **WHEN** an operator clicks Test in the create or edit dialog before saving
- **THEN** the app calls `POST /api/proxies/test`
- **AND** displays testing, working, or failed state without requiring a saved proxy id

#### Scenario: Test saved proxy
- **WHEN** an operator tests a saved proxy row
- **THEN** the app calls `POST /api/proxies/{proxy_id}/test`
- **AND** refreshes the persisted status and test metadata

### Requirement: Account views expose proxy assignment and health

Account list/detail views SHALL show proxy assignment and proxy dependency health beside existing account health signals. Account detail SHALL include a proxy dropdown that can save or clear assignment.

#### Scenario: Account detail saves proxy assignment
- **WHEN** an operator selects a proxy in account detail
- **THEN** the app calls `PUT /api/accounts/{account_id}/proxy` with the selected proxy id
- **AND** refreshes account data

#### Scenario: Account list shows proxy problem
- **WHEN** an account has an unavailable proxy dependency
- **THEN** account list/detail views show the proxy name or reason, last test information when available, and an action-needed status

### Requirement: OAuth and re-auth dialogs include proxy dropdown

Add-account OAuth/device dialogs and re-auth dialogs SHALL include a proxy dropdown with `None` plus managed proxy options. Re-auth SHALL preselect the current account proxy and allow clearing it.

#### Scenario: Add-account submits selected proxy
- **WHEN** an operator starts add-account OAuth with a selected proxy
- **THEN** the OAuth start request includes that `proxyId`

#### Scenario: Re-auth preselects current proxy
- **WHEN** an operator opens re-auth for an account with an assigned proxy
- **THEN** the proxy dropdown preselects that proxy
