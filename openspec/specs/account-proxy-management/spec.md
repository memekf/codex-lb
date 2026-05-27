# account-proxy-management Specification

## Purpose

Define managed outbound proxy records, validation, safe storage, testing, and operator-facing API behavior.

## Requirements

### Requirement: Managed proxies are named encrypted records

The system SHALL store outbound proxy definitions as managed `account_proxies` records with `id`, `displayName`, encrypted proxy URL, `status`, `lastTestedAt`, `lastTestError`, `lastTestLatencyMs`, `createdAt`, and `updatedAt`. Persisted proxy URLs MUST support only `http://` and `https://` schemes and MUST be encrypted at rest.

#### Scenario: Create proxy stores encrypted URL
- **WHEN** an operator creates a proxy with a valid HTTP(S) URL
- **THEN** the API returns the created proxy with a redacted URL
- **AND** the database stores the proxy URL encrypted instead of plaintext
- **AND** the saved proxy status is `untested`

#### Scenario: Invalid proxy URL is rejected
- **WHEN** an operator submits a proxy URL with a non-HTTP(S) scheme, missing host, malformed structure, or fragment
- **THEN** the API rejects the request without creating or updating a proxy record

### Requirement: Managed proxy APIs provide CRUD and test operations

The backend SHALL expose `/api/proxies` routes for listing, creating, updating, deleting, testing a draft proxy URL, and testing a saved proxy. API responses MUST redact proxy credentials and MUST NOT expose decrypted proxy URLs.

#### Scenario: Draft proxy test does not persist a row
- **WHEN** an operator tests an unsaved proxy URL
- **THEN** the response reports working or failed status, latency or redacted error details
- **AND** no `account_proxies` row is created or updated

#### Scenario: Saved proxy test persists status
- **WHEN** an operator tests an existing proxy
- **THEN** the proxy status is `testing` while the check is in progress without discarding its prior test metadata
- **THEN** the proxy row stores the new status, last test timestamp, latency when successful, and redacted bounded error when failed

#### Scenario: Delete assigned proxy is rejected
- **WHEN** an operator deletes a proxy currently assigned to one or more accounts
- **THEN** the API rejects the deletion with a clear in-use error
- **AND** existing account proxy assignments remain unchanged

### Requirement: Proxy credential material is redacted from outward surfaces

The system MUST redact proxy credentials from proxy API responses, test results, wrapper errors, and log-facing error messages.

#### Scenario: Failed proxy test redacts credentials
- **WHEN** testing a proxy URL containing embedded credentials fails
- **THEN** the returned error does not contain the username or password from the proxy URL
