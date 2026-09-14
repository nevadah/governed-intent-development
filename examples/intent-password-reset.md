---
unit: auth/password-reset
version: 0.2.0
status: approved
author: nevada.hamaker
reviewers:
  - nevada.hamaker
exposes:
  - POST /auth/password-reset/request
  - POST /auth/password-reset/redeem
depends_on:
  - auth/password-policy
  - auth/session
  - notifications/email-dispatch
must_not_know:
  - auth/oauth
  - auth/magic-link
  - user/profile
tags:
  - security
  - auth
  - user-facing
---

# Intent: Password Reset Flow

## Summary

Allow a user who cannot log in to regain access by requesting a time-limited, single-use reset token delivered via email. The system must not reveal whether an email address has an account.

---

## Domain Semantics

**Reset token** — A cryptographically random, opaque string generated at request time. It is not a password, not a session credential, and carries no user identity in its structure. Its only meaning is: "someone with access to this email address asked to reset their password at a specific point in time."

**Token window** — The period during which a token can be redeemed. Expiry is measured from generation time, not from email delivery. If delivery is delayed, the window still closes at the same wall-clock time.

**Account enumeration** — An attack where an attacker determines whether a given email address has a registered account by observing different system responses. This flow must not enable enumeration: the response to a reset request must be identical whether or not the email exists.

**Redemption** — The act of submitting a valid token and a new password. Successful redemption invalidates the token and updates the credential. It does not log the user in.

---

## Behavioral Contract

### Preconditions

- The requesting client has access to a valid email address (no verification required by this unit — that is the caller's concern).
- The email service dependency is reachable (see `depends_on`).
- Password policy rules are available to validate the new password (see `depends_on`).

### Postconditions

**On successful request (email exists):**
- A reset token is persisted, associated with the account, with a generation timestamp.
- Any previously issued, unused tokens for that account are invalidated.
- An email containing the token (or a link embedding the token) is dispatched to the address.
- The API response is identical to the "email not found" case.

**On successful request (email does not exist):**
- No token is created.
- No email is sent.
- The API response is identical to the "email found" case.

**On successful redemption:**
- The account's password credential is replaced with a hash of the submitted password.
- The token is invalidated and cannot be reused.
- All active sessions for the account are invalidated.
- The user is not automatically authenticated.

**On failed redemption (invalid or expired token):**
- The password credential is unchanged.
- The token is not consumed (expired tokens remain expired; invalid tokens remain invalid).
- The response does not distinguish between "token not found", "token expired", and "token already used".

### Invariants

- At most one valid (unexpired, unused) reset token exists per account at any time.
- A token's expiry window is exactly 90 minutes from generation. This is not configurable per-request.
- Tokens are never logged, never included in server-side analytics events, and never appear in URLs in a context where they could be captured by referrer headers.
- The generation timestamp and expiry are stored server-side; the client is not trusted to supply or extend them.

### Scenarios

```gherkin
Feature: Password Reset Flow

  Scenario: Happy path
    Given a registered account with email "user@example.com"
    When a reset is requested for "user@example.com"
    Then a token is generated and persisted
    And the token is dispatched to "user@example.com"
    And the response indicates the request was received

  Scenario: Unknown email
    Given no account exists for "unknown@example.com"
    When a reset is requested for "unknown@example.com"
    Then no token is generated
    And no email is sent
    And the response is identical to the happy path response

  Scenario: Second request before first token used
    Given a token was issued for an account 10 minutes ago and not yet redeemed
    When a second reset is requested for the same account
    Then a new token is generated
    And the previous token is invalidated
    And the new token is dispatched

  Scenario: Redemption within window
    Given a token issued 45 minutes ago
    When it is submitted with a new password that passes policy validation
    Then the account password is updated
    And the token is consumed and cannot be reused
    And all active sessions for the account are invalidated
    And the user is not authenticated

  Scenario: Redemption after expiry
    Given a token issued 61 minutes ago
    When it is submitted with a valid new password
    Then the password is unchanged
    And the response does not distinguish expiry from invalidity

  Scenario: Reuse of a consumed token
    Given a token that was successfully redeemed
    When it is submitted again
    Then the request fails identically to the expired token case

  Scenario: Invalid new password
    Given a valid unexpired token
    When it is submitted with a password that fails policy validation
    Then the password is unchanged
    And the token is not consumed
    And the validation error is returned

  Scenario: Rate limit per IP exceeded
    Given 10 reset requests have been made from the same IP within 15 minutes
    When an eleventh reset is requested from that IP for any address
    Then no token is generated
    And no email is sent
    And the response does not reveal which rate limit was reached
    And the response does not reveal whether the address has an account

  Scenario: Email delivery failure
    Given a registered account
    And the email service is reachable but failing
    When a reset is requested
    Then no token is persisted
    And the caller receives a 503 error
```

---

## Quality Attributes

```yaml
security:
  token_entropy_bits: 128
  token_source: cryptographically_secure_random
  token_comparison: constant_time
  rate_limits:
    per_email:
      requests: 3
      window_minutes: 15
    per_ip:
      requests: 10
      window_minutes: 15
  rate_limit_response: must_not_reveal_which_limit_hit

performance:
  request_endpoint_p99_ms: 500
  request_email_dispatch: async
  redemption_endpoint_p99_ms: 300

failure_modes:
  token_store_unavailable: return_503_no_token_generated
  email_service_unavailable: return_503_no_token_persisted
  password_policy_unavailable_at_redemption: return_503_no_credential_update
```

---

## Security Model

**Threat actors:**
- Unauthenticated external attackers attempting to enumerate registered accounts, or to brute-force or guess reset tokens.
- An attacker with temporary read access to a victim's inbox (shared device, compromised mail client, forwarded mail).
- An attacker with network observation capability on the email delivery path.
- Automated abuse infrastructure using the request endpoint as a free email-sending relay against third parties.

**Trust boundaries:**
- The email address submitted to the request endpoint is fully untrusted. It is not verified by this unit, may not correspond to an account, and may be supplied at volume by an attacker.
- The token submitted to the redemption endpoint is fully untrusted and must be validated server-side against stored state. No property of the token itself (length, prefix, encoded content) may be treated as evidence of validity.
- The new password submitted at redemption is untrusted and must be validated against `auth/password-policy` before any credential write.
- The email inbox is a trust boundary this unit cannot enforce. Possession of the token is treated as proof of inbox access, and nothing more — which is why redemption does not establish a session.

**Sensitive data handled:**
- **Reset token** — never logged, never emitted in analytics events, never placed where a referrer header could capture it, and never returned in an API response. Stored server-side in a form that is not directly replayable if the store is read (hashed at rest).
- **Email address** — may appear in delivery logs owned by `notifications/email-dispatch`, but must not appear in this unit's error responses, since that would defeat the enumeration guarantee.
- **New password** — never logged in any form, never persisted in plaintext, replaced by a hash before storage.
- **Account existence** — treated as sensitive in its own right. Whether an address has an account is information this unit must not disclose through response body, status code, or response timing.

**Security responsibilities of this unit:**
- Enumeration resistance across every observable channel: response body, status code, and response latency.
- Token generation with at least 128 bits of entropy from a cryptographically secure source.
- Constant-time token comparison at redemption.
- Single-use token semantics and server-authoritative expiry.
- Session invalidation on successful credential change.
- Rate limiting on both the per-email and per-IP dimensions, with a response that does not reveal which limit was reached.

**Explicitly out of scope:**
- Transport security for email delivery — owned by `notifications/email-dispatch`.
- Password strength rules — owned by `auth/password-policy`. This unit enforces that the policy is consulted, not what the policy says.
- Session issuance and lifetime — owned by `auth/session`. This unit only requires that existing sessions are invalidated.
- Detection of a compromised inbox. If an attacker controls the inbox, this flow will behave correctly and the account will still be lost. That risk is mitigated elsewhere, by multi-factor authentication.

---

## Dependencies and Boundaries

**Depends on:**
- `auth/password-policy` — validates the submitted password at redemption. This unit does not define password rules and must not embed a copy of them; if the policy is unavailable, redemption fails closed rather than applying a fallback rule.
- `auth/session` — invalidates all active sessions for the account after a successful credential change. This unit does not own session storage or lifetime.
- `notifications/email-dispatch` — accepts a rendered email and delivers it. This unit does not own delivery mechanics, provider routing, or retry policy.

**Exposes:**
<!-- This prose list mirrors the machine-readable `exposes` field in the frontmatter.
     The frontmatter version is for tooling; this version explains what callers can rely on. -->
- `POST /auth/password-reset/request` — accepts an email address, always returns the same response shape regardless of whether an account exists. Callers must not infer account existence from any property of this response, including its latency.
- `POST /auth/password-reset/redeem` — accepts a token and a new password. On success the credential is replaced and all sessions are invalidated. The caller is not authenticated as a result and must log in separately.

**Must not know about:**
- `auth/oauth` — an account may have a federated identity, but this flow operates purely on the local credential. Branching on OAuth state would leak the existence and type of a linked identity.
- `auth/magic-link` — passwordless login is a separate flow with a separate token lifecycle. Sharing token storage or redemption logic between them would couple two independent security models.
- `user/profile` — no profile data is read or written here. Personalizing the reset email beyond what the template renderer already has would widen the data exposed to an attacker with inbox access.

---

## Rationale

**90-minute expiry, not 15 or 24 hours**
15 minutes creates support burden — users who don't check email promptly face friction. 24 hours creates an unacceptably wide window where a compromised inbox can be exploited without the account owner noticing. The window opened at 60 minutes and was widened to 90 in v0.2.0 after support data showed mobile users were losing tokens to delayed inbox checks; the security team accepted the wider window on the strength of the existing per-email rate limit.

**No automatic login after redemption**
Automatically logging in after reset conflates credential recovery with session establishment. It also creates a vector where anyone with brief inbox access can establish a session that persists beyond the reset window. Requiring explicit login after reset keeps the flows cleanly separated.

**Atomic token-or-error on email failure**
Persisting a token that was never delivered creates a phantom: the token exists in the store but the user has no way to retrieve it. The next request will invalidate it, but in the window between, support requests are unanswerable. Atomic behavior eliminates this state entirely.

**Magic links considered and rejected**
A pure magic link (clicked link logs user in directly) conflates reset with authentication, creates session-from-inbox access, and is harder to scope correctly. Token-in-link (link opens a form, user submits token + new password) keeps reset as credential replacement only.

**One valid token per account**
Allowing multiple valid tokens widens the window for inbox-compromise attacks and creates ambiguity about which request was most recent. Invalidating prior tokens on new request is a minor UX cost with a clear security benefit.

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
  date: 2026-05-08
  classification: non-breaking
  trigger: stakeholder_request
  changed_by: nevada.hamaker
  changes:
    - "[MODIFIED] Invariants — Token expiry window extended from 60 to 90 minutes"
    - "[ADDED] Scenario: Rate limit per IP exceeded — missing security scenario added"
  reason: >
    Support data showed 18% of reset requests were abandoned after token expiry,
    predominantly from mobile users checking email on a delay. Extended to 90 minutes
    after confirming the security team accepted the wider window given the existing
    per-email rate limiting. Rate limit IP scenario added after elicitation review of
    auth/session flagged the gap.

- version: 0.3.0
  date: 2026-09-13
  classification: non-breaking
  trigger: elicitation_report
  changed_by: nevada.hamaker
  changes:
    - "[ADDED] Security Model — threat actors, trust boundaries, sensitive data handling, and explicit out-of-scope items"
    - "[ADDED] Dependencies and Boundaries — prose section reconciling the depends_on, exposes and must_not_know frontmatter"
  reason: >
    The document declared depends_on and must_not_know in frontmatter with no prose
    section explaining them, which is the mismatch the elicitation agent's
    BOUNDARY_UNCLEAR flag exists to catch. The Security Model section was added to the
    template when the security stage joined the pipeline and this document predated it;
    without it the Security Agent has no declared scope to audit against.
```
