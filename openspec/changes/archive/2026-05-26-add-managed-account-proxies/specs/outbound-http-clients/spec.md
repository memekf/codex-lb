## ADDED Requirements

### Requirement: Account-bound transports resolve managed proxy at final outbound call

Account-bound upstream HTTP and WebSocket transports SHALL accept the local codex-lb account id and resolve the latest account proxy assignment at the final outbound transport primitive. The wrapper SHALL reject missing, paused, or deactivated accounts before making upstream calls.

#### Scenario: Current proxy assignment is used for HTTP request
- **WHEN** an account-bound HTTP request is sent for an account assigned to a working proxy
- **THEN** the final outbound HTTP client uses that proxy URL for the request

#### Scenario: Changed assignment is reloaded
- **WHEN** a scheduler or caller holds stale account data
- **AND** the account proxy assignment changes before the final outbound call
- **THEN** the final account-bound transport resolves the latest assignment from storage

### Requirement: Assigned proxy transport fails closed when unusable

Account-bound transport SHALL NOT fall back to direct traffic when an account has an assigned proxy that is missing, invalid, undecryptable, deleted, unresolved, or marked `failed`.

#### Scenario: Missing assigned proxy fails closed
- **WHEN** an account-bound request is sent for an account whose assigned proxy row is missing
- **THEN** the wrapper rejects the request before direct upstream traffic can be sent

#### Scenario: Failed assigned proxy fails closed
- **WHEN** an account-bound request is sent for an account whose assigned proxy status is `failed`
- **THEN** the wrapper rejects the request before direct upstream traffic can be sent

#### Scenario: Previously failed assigned proxy remains fail closed during retest
- **WHEN** an account-bound request is sent while its assigned proxy is `testing` after a failed result
- **THEN** the wrapper rejects the request before direct upstream traffic can be sent

### Requirement: Pre-account OAuth/device calls use flow proxy snapshot

OAuth authorize, device-code polling, and token-exchange calls that occur before an account exists SHALL use the proxy URL snapshot stored in the auth flow state rather than account-bound proxy resolution.

#### Scenario: Device polling uses selected proxy snapshot
- **WHEN** a device login flow starts with a selected proxy id
- **THEN** token polling for that flow uses the resolved proxy URL snapshot from flow state
