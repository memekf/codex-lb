## ADDED Requirements

### Requirement: Account-bound long-lived sessions validate transport fingerprints

Native upstream WebSocket sessions and HTTP bridge sessions SHALL store the effective account transport fingerprint from connection creation and SHALL assert that the stored fingerprint still matches the current account proxy assignment before later sends, reuse, replay, prewarm, reconnect, or response creation.

#### Scenario: Account proxy assignment change invalidates stored fingerprint
- **WHEN** a long-lived session was opened while an account had no proxy assignment
- **AND** the account is later assigned to a managed proxy
- **THEN** later account-bound use of that session fails closed or reconnects only after validating the new fingerprint

#### Scenario: Proxy URL update invalidates stored fingerprint
- **WHEN** a long-lived session was opened through a managed proxy
- **AND** that proxy record's URL is changed
- **THEN** later account-bound use of the old session fails closed instead of using the old proxy URL

### Requirement: Proxy changes close affected local bridge sessions

Account proxy assignment updates SHALL close local HTTP bridge sessions for that account. Managed proxy URL updates SHALL close local HTTP bridge sessions for all accounts assigned to that proxy.

#### Scenario: Assignment update closes bridge sessions
- **WHEN** an operator changes or clears an account proxy assignment
- **THEN** local HTTP bridge sessions for that account are closed

#### Scenario: Proxy URL update closes assigned account sessions
- **WHEN** an operator changes a managed proxy URL
- **THEN** local HTTP bridge sessions for every account assigned to that proxy are closed
