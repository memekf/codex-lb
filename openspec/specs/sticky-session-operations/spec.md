# sticky-session-operations Specification

## Purpose

Define sticky-session operation contracts so durable sessions, dashboard affinity, and prompt-cache affinity stay distinct.
## Requirements
### Requirement: Sticky sessions are explicitly typed
The system SHALL persist each sticky-session mapping with an explicit kind so durable Codex backend affinity, durable dashboard sticky-thread routing, and bounded prompt-cache affinity can be managed independently.

#### Scenario: Backend Codex session affinity is stored as durable
- **WHEN** a backend Codex request creates or refreshes stickiness from `session_id`
- **THEN** the stored mapping kind is `codex_session`

#### Scenario: Backend Codex session rebinds under budget pressure
- **WHEN** a backend Codex request resolves an existing `codex_session` mapping
- **AND** the pinned account is above the configured sticky reallocation budget threshold
- **AND** another eligible account remains below that threshold
- **THEN** selection rebinds the durable `codex_session` mapping to the healthier account before sending the request upstream

#### Scenario: Dashboard sticky thread routing is stored as durable
- **WHEN** sticky-thread routing creates or refreshes stickiness from a prompt-derived key
- **THEN** the stored mapping kind is `sticky_thread`

#### Scenario: OpenAI prompt-cache affinity is stored as bounded
- **WHEN** an OpenAI-style request creates or refreshes prompt-cache affinity
- **THEN** the stored mapping kind is `prompt_cache`

#### Scenario: Identical keys remain isolated across sticky-session kinds
- **WHEN** the same sticky-session key value is used for more than one kind
- **THEN** each `(key, kind)` mapping is stored and managed independently without overwriting the others

### Requirement: Dashboard exposes sticky-session administration
The system SHALL provide dashboard APIs for listing sticky-session mappings, deleting one mapping, and purging stale mappings.

#### Scenario: List sticky-session mappings
- **WHEN** the dashboard requests sticky-session entries
- **THEN** the response includes each mapping's `key`, `account_id`, `kind`, `created_at`, `updated_at`, `expires_at`, and `is_stale`
- **AND** the response includes the total number of stale `prompt_cache` mappings that currently exist beyond the returned page

#### Scenario: List only stale mappings
- **WHEN** the dashboard requests sticky-session entries with `staleOnly=true`
- **THEN** the system applies stale prompt-cache filtering before enforcing the result limit

#### Scenario: Delete one mapping
- **WHEN** the dashboard deletes a sticky-session mapping by both `key` and `kind`
- **THEN** the system removes that mapping and returns a success response

#### Scenario: Purge stale prompt-cache mappings
- **WHEN** the dashboard requests a stale purge
- **THEN** the system deletes only stale `prompt_cache` mappings and leaves durable mappings untouched

### Requirement: Prompt-cache mappings are cleaned up proactively
The system SHALL run a background cleanup loop that deletes stale `prompt_cache` mappings using the current dashboard prompt-cache affinity TTL.

#### Scenario: Cleanup loop removes stale prompt-cache mappings
- **WHEN** the cleanup loop runs and finds `prompt_cache` mappings older than the configured TTL
- **THEN** it deletes those mappings

#### Scenario: Cleanup loop preserves durable mappings
- **WHEN** the cleanup loop runs
- **THEN** it does not delete `codex_session` or `sticky_thread` mappings regardless of age

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
