## ADDED Requirements

### Requirement: Long-lived sessions are soft across active timeframe boundaries

Existing native upstream WebSocket sessions and HTTP bridge sessions SHALL NOT be closed or rejected solely because the current time moves outside an assigned active timeframe after session creation. New session creation remains subject to account-bound transport timeframe enforcement.

#### Scenario: Existing session reuse is not rejected by clock boundary alone
- **WHEN** a long-lived session was created while an account was inside its active timeframe
- **AND** the current time later moves outside the timeframe
- **THEN** reuse or send on that existing session is not rejected solely because of the schedule boundary

#### Scenario: New long-lived session creation is gated
- **WHEN** a new native upstream WebSocket or HTTP bridge session is created for an account outside its assigned active timeframe
- **THEN** session creation fails closed through the account-bound transport gate
