# CI/CD Integration

## Overview

The Governed Intent Development workflow has four CI gates. One runs on intent documents; three run on generated code. Together they enforce the methodology's core constraints automatically: intent must be valid before code exists, it must be approved before that code can merge, generated code must satisfy its intent, and generated code must pass an adversarial security audit.

All four are implemented in [`scripts/`](../scripts/). The first two need nothing but Python; the last two call a model.

---

## The four CI gates

| Gate | Trigger | What it checks | Blocks merge? |
|---|---|---|---|
| **Intent document validation** | PR touching `intent/` or `examples/` | Frontmatter parses and conforms to schema | Yes |
| **Intent document status** | PR containing generated implementation | Every changed unit has an intent document in `approved` status | Yes |
| **Compliance check** | PR containing generated implementation | Implementation satisfies the intent document | Yes (FAIL); No (UNVERIFIABLE) |
| **Security audit** | PR containing generated implementation | Implementation has no statically detectable vulnerabilities | Yes (VULNERABILITY); No (UNVERIFIABLE) |

These are distinct checks for distinct failures. Schema validation catches structural problems. The status check catches code that reached the merge boundary without an approved document behind it. The compliance check catches semantic divergence from declared intent. The security audit catches vulnerability classes that are not declared in the intent document — the implementation may correctly reflect the intent while still being insecure.

---

## Gate 1: Intent document validation

Validates that every intent document in the repository has well-formed frontmatter that conforms to the JSON schema in `schema/intent-document.schema.json`.

**When to run:** On any PR that touches files in `intent/`, `examples/`, or `schema/`.

**Gate behavior:** Fails the check and blocks merge if any document fails schema validation.

**Reference implementation:** This repository uses this gate. See [`.github/workflows/validate-intent.yml`](../.github/workflows/validate-intent.yml) and [`scripts/validate-intent.py`](../scripts/validate-intent.py) for a working example.

The other three gates are implemented in [`scripts/`](../scripts/) and wired together in [`intent-gates.example.yml`](intent-gates.example.yml), which is an example rather than an active workflow because this repository defines the methodology and generates no code — there is nothing here for them to check.

---

## Gate 2: Compliance check

Invokes the Compliance Agent against the generated implementation and its corresponding intent document. This requires an LLM API call and is therefore different in kind from a conventional CI check.

**When to run:** On any PR that includes generated implementation files (typically files in `src/` or your project's equivalent).

**Gate behavior:**
- `FAIL` result — blocks merge. The implementation diverges from the intent document. The correct response is to regenerate, not to patch the code.
- `UNVERIFIABLE` items — surface as annotations or warnings, do not block merge. These require runtime verification (load testing, security scanning) that static analysis cannot provide.
- `PASS` result — check succeeds.

**How to invoke:** [`scripts/run_intent_gate.py`](../scripts/run_intent_gate.py) runs the agent headlessly and exits non-zero on `FAIL`:

```bash
python scripts/run_intent_gate.py compliance     --intent intent/auth/password-reset.md     --implementation src/auth/password-reset
```

It reads the agent's system prompt from [`agents/compliance-agent.md`](../agents/compliance-agent.md), invokes `claude -p` with read-only tools, prints the report, and parses its `Result` line for the gate decision. The API key is supplied as `ANTHROPIC_API_KEY` from a repository secret.

The read-only tool restriction is load-bearing rather than defensive: an agent that can edit the implementation it is judging is not an independent check. See [`workflow/intent-gates.example.yml`](intent-gates.example.yml) for a complete workflow.

**Surfacing findings:** Post the compliance report as a PR comment or job summary so reviewers can see the specific findings without reading raw CI logs. UNVERIFIABLE items should be visible but clearly labeled as not blocking.

---

## Gate 3: Security audit

Invokes the Security Agent against the generated implementation and its corresponding intent document. Like the compliance check, this requires an LLM API call.

**When to run:** On any PR that includes generated implementation files, after the compliance check passes.

**Gate behavior:**
- `VULNERABILITY` result — blocks merge. Routes to intent update + regeneration (if the vulnerability reveals an intent gap) or regeneration alone (if the intent specifies the security property but the generated code violates it).
- `UNVERIFIABLE` items — surface as annotations or warnings, do not block merge. Document for pre-production runtime verification or penetration testing.
- `PASS` result — check succeeds.

**How to invoke:** The same runner, with the `security` gate:

```bash
python scripts/run_intent_gate.py security     --intent intent/auth/password-reset.md     --implementation src/auth/password-reset
```

It exits non-zero on `FINDINGS`. Run it only after the compliance gate passes — auditing an implementation that does not yet match its intent document wastes the audit.

**On model selection:** If a model with security research specialization is available in your environment, use it for this check rather than the general-purpose model used for compliance; pass it with `--model`. See [`agents/README.md`](../agents/README.md#a-note-on-model-selection-for-the-security-agent) for details.

**Surfacing findings:** Post the security audit report as a PR comment or job summary. VULNERABILITY findings with intent gaps should be clearly identified — they require an intent document update before regeneration, not just a re-run of generation.

---

## Intent document status enforcement

A CI check can verify that every implementation file being merged has a corresponding intent document in `approved` status. This prevents generated code from reaching the main branch when its intent document is still `draft` or `review`.

**Implementation:** [`scripts/check_intent_status.py`](../scripts/check_intent_status.py). For each implementation unit changed in a PR it resolves the corresponding intent document by path convention (`src/auth/password-reset/` → `intent/auth/password-reset.md`) and asserts that its `status` field is `approved`:

```bash
python scripts/check_intent_status.py src/auth/password-reset
```

Projects that map differently override the roots with `--implementation-root` and `--intent-root`.

**When to run:** On any PR containing files in the implementation directory.

**Gate behavior:** Blocks merge if a corresponding intent document is missing or not in `approved` status.

This gate needs no model and no API key, which makes it the one to adopt first. It is also the durable backstop for the [read-only hook](../hooks/): the hook governs agent behavior inside a session, while this check governs what reaches the merge boundary regardless of how it got there.

This check enforces at the merge boundary what the workflow enforces by process: code generation cannot begin until the intent document is approved.

---

## Branch protection recommendations

For a repository using this methodology, the following branch protection rules on `main` enforce the workflow:

```
Require status checks to pass before merging:
  - Intent document validation
  - Intent document status
  - Compliance check
  - Security audit

Require branches to be up to date before merging: Yes
Do not allow bypassing the above settings: Yes
Allow force pushes: No
Allow deletions: No
```

The "do not allow bypassing" setting (enforce for administrators) is important: a methodology that can be bypassed by the same person who set it up is not a governed methodology.

---

## Connecting generation to the pipeline

Code generation (Stage 6) is typically triggered locally or in a dedicated environment — not as part of the standard PR pipeline. The recommended pattern:

1. The engineer triggers generation against an approved intent document
2. The AI agent generates an implementation and commits it to a feature branch
3. The engineer opens a PR from the feature branch to `main`
4. The compliance check runs automatically on the PR
5. The security audit runs automatically on the PR
6. On compliance pass and security audit pass, the PR can merge

This keeps the CI pipeline as a verification layer rather than a generation trigger. Generation on demand, compliance on every PR.

---

## Failure handling

| Situation | Correct response |
|---|---|
| Schema validation fails | Fix the intent document frontmatter before advancing |
| Compliance `FAIL` — implementation diverges from intent | Regenerate from the intent document; do not patch the code |
| Compliance `FAIL` — intent document has internal conflict (Document Integrity section) | Return the intent document to Stage 3 (Intent Review Agent) before regenerating |
| Compliance `UNVERIFIABLE` | Note for runtime verification; does not block merge |
| Security `VULNERABILITY` with intent gap | Update the intent document via the Intent Maintenance Agent, then regenerate |
| Security `VULNERABILITY` without intent gap | Regenerate from the existing intent document |
| Security `UNVERIFIABLE` | Document for pre-production penetration testing or runtime verification; does not block merge |
| Intent document not `approved` | Complete the review workflow before generating |

**Neither the compliance agent nor the security agent determines whether the intent was right** — only whether the implementation matches it, and whether the implementation is secure. Failures that reveal a gap in the intent should route through the Intent Maintenance Agent before any regeneration.
