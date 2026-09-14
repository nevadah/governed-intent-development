---
unit: notifications/welcome-email
version: 0.2.0
status: approved
author: nevada.hamaker
reviewers:
  - nevada.hamaker
exposes:
  - UserWelcomeEmailSent (event)
depends_on:
  - user/account
  - notifications/email-dispatch
  - notifications/template-renderer
must_not_know:
  - auth/session
  - payments/billing
  - user/preferences
tags:
  - event-driven
  - async
  - notifications
---

# Intent: Welcome Email

## Summary

Send a welcome email to a newly registered user in response to a `UserRegistered` event. This unit has no synchronous caller — it is triggered by an event and produces a side effect (an email). It exposes a `UserWelcomeEmailSent` event on successful dispatch and is designed to be safe to retry.

---

## Domain Semantics

**Trigger event** — `UserRegistered`: emitted by `user/account` when a new user account is successfully created. Contains the user's account ID and the email address supplied at registration. This unit does not validate the email address — it trusts the trigger event, which was emitted by a unit that owns that validation.

**Welcome email** — A single transactional email sent once per registered account. Its content is rendered from a template owned by `notifications/template-renderer`. This unit does not own the template or its content.

**Idempotency** — The property of producing the same outcome when the same operation is performed more than once. This unit must be idempotent: if `UserRegistered` is delivered more than once for the same account (due to at-least-once event delivery), only one welcome email must be sent.

**Sent record** — A persisted record indicating that a welcome email was dispatched for a given account ID. Used to enforce idempotency. The record is written atomically with the dispatch confirmation.

**At-least-once delivery** — The event infrastructure guarantees that `UserRegistered` will be delivered at least once, but may deliver it more than once. This unit must handle duplicate delivery correctly.

**Dead letter** — An event that has failed processing beyond the retry limit and has been moved to a dead letter queue for manual inspection. Deadlettered events are not retried automatically.

---

## Behavioral Contract

### Preconditions

- A `UserRegistered` event has been received containing a valid account ID and email address.
- `user/account` is reachable (used to fetch display name for the email).
- `notifications/template-renderer` is reachable.
- `notifications/email-dispatch` is reachable.

### Postconditions

**On successful first dispatch:**
- A welcome email is dispatched to the address in the trigger event.
- A sent record is persisted for the account ID.
- A `UserWelcomeEmailSent` event is emitted containing the account ID and dispatch timestamp.
- The trigger event is acknowledged (removed from the processing queue).

**On duplicate event (sent record already exists for this account ID):**
- No email is dispatched.
- No new `UserWelcomeEmailSent` event is emitted.
- The duplicate trigger event is acknowledged (not an error — idempotent processing).

**On dispatch failure (email service error):**
- No sent record is persisted.
- No `UserWelcomeEmailSent` event is emitted.
- The trigger event is not acknowledged — it will be redelivered after the retry backoff.
- After exceeding the retry limit, the event is moved to the dead letter queue.

**On dependency failure (user/account or template-renderer unavailable):**
- Same behavior as dispatch failure: no acknowledgement, retry will occur.

### Invariants

- At most one welcome email is sent per account ID, ever. The sent record is the enforcement mechanism.
- The sent record and the dispatch are atomic: a record is never written without a confirmed dispatch, and a dispatch is never made without a subsequent record write. If the record write fails after a successful dispatch, the operation is treated as failed — the next retry will attempt dispatch again. The email service must be idempotent at the dispatch layer to handle this case.
- This unit never reads or writes user authentication state, billing state, or preference data.
- The content of the welcome email is entirely determined by `notifications/template-renderer`. This unit passes the account ID and display name; it does not construct or modify email content.

### Scenarios

```gherkin
Feature: Welcome Email

  # --- Happy path ---

  Scenario: First-time delivery sends email and records dispatch
    Given a UserRegistered event for account "acc-123" with email "alice@example.com"
    And no sent record exists for "acc-123"
    When the event is processed
    Then a welcome email is dispatched to "alice@example.com"
    And a sent record is persisted for "acc-123"
    And a UserWelcomeEmailSent event is emitted for "acc-123"
    And the trigger event is acknowledged

  # --- Edge cases ---

  Scenario: Duplicate event is processed idempotently
    Given a UserRegistered event for account "acc-123"
    And a sent record already exists for "acc-123"
    When the duplicate event is processed
    Then no email is dispatched
    And no UserWelcomeEmailSent event is emitted
    And the duplicate event is acknowledged without error

  Scenario: Retry after previous partial failure
    Given a UserRegistered event for account "acc-456"
    And no sent record exists for "acc-456"
    And a previous attempt dispatched the email but failed to write the sent record
    When the event is redelivered and processed
    Then a welcome email is dispatched again to the address in the event
    And a sent record is persisted for "acc-456"
    And the event is acknowledged
    And the email service handles the duplicate dispatch idempotently

  # --- Failure modes ---

  Scenario: Email dispatch fails transiently
    Given a UserRegistered event for account "acc-789"
    And the email dispatch service returns a transient error
    When the event is processed
    Then no sent record is written
    And no UserWelcomeEmailSent event is emitted
    And the trigger event is not acknowledged
    And the event will be redelivered after the retry backoff

  Scenario: Event exceeds retry limit and is deadlettered
    Given a UserRegistered event that has failed processing 5 consecutive times
    When the retry limit is exceeded
    Then the event is moved to the dead letter queue
    And no email has been sent
    And no sent record exists for the account
    And no further automatic retry occurs

  Scenario: User account lookup fails
    Given a UserRegistered event for account "acc-101"
    And the user/account dependency is unreachable
    When the event is processed
    Then no email is dispatched
    And the event is not acknowledged
    And the event will be redelivered after retry backoff

  Scenario: Template renderer fails
    Given a UserRegistered event for account "acc-202"
    And the notifications/template-renderer dependency is unreachable
    When the event is processed
    Then no email is dispatched
    And the event is not acknowledged

  # --- Security-relevant paths ---

  Scenario: Event contains email address not matching account record
    Given a UserRegistered event for account "acc-303" with email "attacker@evil.com"
    And the account record for "acc-303" has email "victim@example.com"
    When the event is processed
    Then the email is dispatched to the address in the account record, not the event
    And the event-supplied email address is not used

  Scenario: Duplicate event cannot cause a second email after sent record exists
    Given a sent record exists for "acc-123"
    When 10 duplicate UserRegistered events for "acc-123" are processed concurrently
    Then exactly zero additional emails are dispatched
    And all 10 events are acknowledged
```

---

## Quality Attributes

```yaml
reliability:
  delivery_guarantee: at_least_once
  idempotency: required
  retry_policy:
    max_attempts: 5
    backoff: exponential
    initial_backoff_seconds: 30
    max_backoff_seconds: 300
  dead_letter_queue: required

performance:
  processing_latency_p99_ms: 2000
  note: >
    Latency is measured from event receipt to acknowledgement.
    Email delivery time is not included — dispatch is fire-and-forget
    once the email service accepts the request.

failure_modes:
  email_dispatch_unavailable: do_not_acknowledge_retry_will_occur
  user_account_unavailable: do_not_acknowledge_retry_will_occur
  template_renderer_unavailable: do_not_acknowledge_retry_will_occur
  sent_record_store_unavailable: do_not_acknowledge_retry_will_occur
  retry_limit_exceeded: move_to_dead_letter_queue

observability:
  emit_event_on_success: UserWelcomeEmailSent
  log_on_duplicate_skip: true
  log_on_deadletter: true
  alert_on_deadletter: true
```

---

## Security Model

**Threat actors:**
- An attacker able to publish onto the event bus, forging a `UserRegistered` event to direct a welcome email at an address they choose.
- An attacker able to replay a legitimate event repeatedly, using the unit as an email amplifier against a real user.
- An internal caller with access to logs or the dead letter queue, which carry account identifiers and may carry email addresses.

**Trust boundaries:**
- The `UserRegistered` event is untrusted. It crosses a service boundary and this unit cannot verify who published it. Every field on it is treated as a hint, not a fact.
- The event's email address field is the sharpest case: it is deliberately ignored. The authoritative address is read from `user/account` using the event's `account_id`. An event carrying a mismatched address therefore cannot redirect mail.
- The event infrastructure guarantees at-least-once delivery, so duplicate events are expected rather than exceptional. Idempotency is owned here, via the sent record, rather than assumed from the infrastructure.

**Sensitive data handled:**
- **Email address** — read from `user/account`, passed to `notifications/email-dispatch`, never persisted by this unit, and never written to this unit's own logs. The sent record stores `account_id`, not the address.
- **Display name** — PII of low sensitivity, obtained from `user/account` at render time and not retained after dispatch.
- **Dead letter queue payloads** — must carry `account_id` and failure context only. An address in a DLQ payload persists PII in an operational store with a different access model and retention policy than the account record.

**Security responsibilities of this unit:**
- Resolving the recipient from the account record rather than from the event, which is what makes event spoofing ineffective.
- Idempotency, so that a replayed event cannot be used to send mail repeatedly to a real user.
- Bounded retries with a dead letter queue, so that failure is observable rather than silent.
- Keeping email addresses out of this unit's logs, metrics, and DLQ payloads.

**Explicitly out of scope:**
- Authentication of event publishers — owned by the event bus. This unit assumes publishers may be hostile and is designed so that a forged event achieves nothing beyond a redundant email to the legitimate account holder.
- Transport security and provider routing for delivery — owned by `notifications/email-dispatch`.
- Email content and localization — owned by `notifications/template-renderer`. A template injection vector would be that unit's finding, not this one's.
- Opt-out and preference enforcement — `user/preferences` is an explicit `must_not_know` boundary; the welcome email is transactional and unconditional on registration.
---

## Dependencies and Boundaries

**Depends on:**
- `user/account` — fetches the user's display name for use in the email template. The email address used for dispatch comes from the account record, not the trigger event, to prevent event-spoofing.
- `notifications/email-dispatch` — accepts a rendered email and delivers it. This unit does not own delivery mechanics or provider routing.
- `notifications/template-renderer` — renders the welcome email template given an account ID and display name. This unit does not own template content or localization.

**Exposes:**
<!-- This prose list mirrors the machine-readable `exposes` field in the frontmatter.
     The frontmatter version is for tooling; this version explains what callers can rely on. -->
- `UserWelcomeEmailSent` (event) — emitted after successful dispatch. Contains: `account_id`, `dispatched_at` timestamp. Downstream consumers (e.g., onboarding workflows) may subscribe to this event to trigger next steps.

**Must not know about:**
- `auth/session` — session state is irrelevant to welcome email dispatch
- `payments/billing` — billing state must not gate or delay welcome email sending
- `user/preferences` — email preferences (opt-out, language) are a separate concern layered over this unit; the welcome email is unconditional on registration

---

## Rationale

**Email address comes from account record, not the trigger event**
The `UserRegistered` event includes the email address as a convenience, but using it directly creates a spoofing vector: a malformed or malicious event could supply a different address. The authoritative source is the account record in `user/account`. The event-supplied address is ignored.

**Idempotency via sent record rather than event deduplication**
Event deduplication at the infrastructure layer (e.g., exactly-once semantics) is not assumed — the event infrastructure guarantees at-least-once. Rather than relying on infrastructure guarantees, this unit owns its idempotency explicitly via the sent record. This makes the behavior observable and testable independently of the event infrastructure.

**Atomicity of sent record and dispatch**
The record write fails after a successful dispatch in the failure scenario (Scenario: Retry after previous partial failure). This means the email service must handle duplicate sends gracefully. This is an explicit design choice: it is better to accept a rare duplicate email than to risk a lost welcome email by treating an unconfirmed dispatch as complete.

**No preference-based opt-out on welcome email**
Welcome email is a transactional notification directly tied to the registration action the user just completed. It is not a marketing email. Preference-based opt-out does not apply. If legal requirements in a specific jurisdiction require otherwise, that is a compliance concern addressed at the `notifications/email-dispatch` layer, not here.

**Dead letter queue required**
Silent failure is worse than visible failure for event-driven workflows. If a welcome email cannot be sent after the retry limit, the failure must be observable and actionable. A dead letter queue with alerting provides that visibility.

---

## Changelog

```yaml
- version: 0.1.0
  date: 2026-05-08
  classification: initial
  changed_by: nevada.hamaker
  changes: []
  reason: Initial approved version.

- version: 0.2.0
  date: 2026-09-13
  classification: non-breaking
  trigger: elicitation_report
  changed_by: nevada.hamaker
  changes:
    - "[ADDED] Security Model — event-spoofing and replay threat model, trust boundaries, PII handling, and out-of-scope items"
  reason: >
    The Security Model section was added to the intent document template when the
    security audit stage joined the pipeline, and this document predated it. Without
    a declared security scope the Security Agent has nothing to audit against and the
    Elicitation Agent cannot check for missing security scenarios.
```
