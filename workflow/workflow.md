# Governed Intent Development Workflow

## Overview

The workflow governs the lifecycle of an intent document from initial authoring through code generation and compliance verification. It is analogous to Gitflow: stages are explicit, gates between them are enforced, and moving backward is intentional (not accidental).

The fundamental constraint: **code generation cannot begin until an intent document reaches `approved` status. Generated code is never manually edited — doing so severs the chain between intent and implementation.**

---

## Diagram

```mermaid
flowchart TD
    A([Business need / change request]) --> B

    subgraph AUTHORING ["Stage 1 · Authoring"]
        B[Author drafts intent document]
        B --> B1{Schema valid?\nAll sections present?}
        B1 -- No --> B
        B1 -- Yes --> C
    end

    subgraph ELICITATION ["Stage 2 · Elicitation"]
        C[Elicitation Agent reviews draft]
        C --> C1{Ambiguities or\ngaps flagged?}
        C1 -- Yes: author revises --> B
        C1 -- No --> D
    end

    subgraph AGENT_REVIEW ["Stage 3 · Agent Review"]
        D[Intent Review Agent stress-tests document]
        D --> D1{Contradictions,\nmissing constraints,\nboundary gaps?}
        D1 -- Yes: author revises --> B
        D1 -- No --> E
    end

    subgraph STAKEHOLDER ["Stage 4 · Stakeholder Review"]
        E[Business stakeholder reviews]
        E --> E1{"Is this what\nthe business needs?"}
        E1 -- No: return with feedback --> B
        E1 -- Yes: sign off --> F
    end

    subgraph ENG_REVIEW ["Stage 5 · Engineering Review"]
        F[Engineer reviews]
        F --> F1{"Is this precise enough\nfor the AI to implement\ncorrectly?"}
        F1 -- No: return for revision --> B
        F1 -- Yes: approve --> G
    end

    subgraph GENERATION ["Stage 6 · Code Generation"]
        G[Status set to 'approved']
        G --> H[AI agent generates implementation]
        H --> H1{Manual edits\nattempted?}
        H1 -- Yes: STOP — update intent instead --> B
        H1 -- No --> I
    end

    subgraph COMPLIANCE ["Stage 7 · Compliance Check"]
        I[Compliance Agent verifies implementation\nagainst intent document]
        I --> I1{All behavioral contracts,\ninvariants, and quality\nattributes satisfied?}
        I1 -- No: regenerate --> H
        I1 -- Yes --> J
    end

    subgraph SECURITY ["Stage 8 · Security Audit"]
        J[Security Agent audits implementation\nadversarially]
        J --> J1{Vulnerability\nfindings?}
        J1 -- "Yes: update intent\n+ regenerate" --> B
        J1 -- No --> K
    end

    K([Complete])

    style AUTHORING fill:#f0f4ff,stroke:#c0c8e8
    style ELICITATION fill:#f0f4ff,stroke:#c0c8e8
    style AGENT_REVIEW fill:#f0f4ff,stroke:#c0c8e8
    style STAKEHOLDER fill:#fff4e0,stroke:#e8d0a0
    style ENG_REVIEW fill:#fff4e0,stroke:#e8d0a0
    style GENERATION fill:#f0fff4,stroke:#a0e8b0
    style COMPLIANCE fill:#f0fff4,stroke:#a0e8b0
    style SECURITY fill:#fff0f0,stroke:#e8a0a0
```

---

## Stages

### Stage 1 · Authoring

**Actor:** Engineer or business stakeholder  
**Input:** A business need, feature request, or change request — expressed in any form  
**Output:** A draft intent document that passes schema validation and contains all required sections

The author is responsible for an initial attempt at capturing intent. The document does not need to be complete or unambiguous at this stage — that is what elicitation is for. It must be structurally valid (frontmatter parses against the JSON schema, no required sections missing) before advancing.

**Exit gate:** Schema validation passes. `status` is `draft`.

---

### Stage 2 · Elicitation

**Actor:** Intent Elicitation Agent  
**Input:** Draft intent document  
**Output:** Elicitation report listing ambiguities, underspecified edge cases, implicit assumptions, and missing coverage

The Elicitation Agent interviews the document rather than the author. It does not rewrite the document — it produces a structured report of what is unclear or absent. The author then revises the intent document in response. This loop repeats until the agent produces a clean report.

**Loop escalation:** If the document has not produced a clean elicitation report after three passes, stop looping and escalate directly to Stage 5 · Engineering Review. A document that cannot clear elicitation after three attempts has a structural problem — continued iteration with the agent is unlikely to resolve it. The engineer reviews the document in its current state and provides direct guidance to the author before elicitation resumes.

**Exit gate:** Elicitation report contains no unresolved flags. Author has addressed every item. The document re-passes schema validation after revisions.

---

### Stage 3 · Agent Review

**Actor:** Intent Review Agent  
**Input:** Elicitation-complete intent document  
**Output:** Review report identifying internal contradictions, missing constraints, logical gaps, and boundary conditions not covered by scenarios

Where the Elicitation Agent finds what is missing, the Intent Review Agent stress-tests what is present. It looks for: scenarios that contradict invariants, postconditions that cannot be satisfied given the preconditions, quality attribute thresholds that conflict with stated dependencies, and `must_not_know` boundaries that the intent document itself violates.

**Exit gate:** Review report contains no unresolved issues. Author has addressed every item.

---

### Stage 4 · Stakeholder Review

**Actor:** Business stakeholder  
**Input:** Agent-reviewed intent document  
**Question:** *Is this what the business needs?*

This is the first of two human review seams. The stakeholder is reviewing for semantic correctness — does the intent document accurately reflect the business outcome required? The stakeholder is not expected to evaluate technical precision or implementation feasibility. If the stakeholder returns the document, it goes back to Stage 1 (authoring) with their feedback.

On approval: the stakeholder's identity is added to the `reviewers` field. `status` advances to `review`.

**Exit gate:** Stakeholder sign-off. `status` is `review`.

---

### Stage 5 · Engineering Review

**Actor:** Engineer  
**Input:** Stakeholder-approved intent document (`status: review`)  
**Question:** *Is this precise enough for the AI to implement correctly?*

This is the second human review seam. The engineer is reviewing for implementation precision — are the behavioral contracts unambiguous? Are the quality attribute thresholds measurable? Are the dependency boundaries enforceable? Are the scenarios complete enough that an agent could generate correct, verifiable code without making assumptions?

The engineer does not review generated code. Review happens here, at the intent level, before any code exists. If the engineer returns the document, it goes back to Stage 1.

On approval: the engineer's identity is added to `reviewers`. `status` advances to `approved`.

**Exit gate:** Engineer sign-off. `status` is `approved`.

---

### Stage 6 · Code Generation

**Actor:** AI coding agent  
**Input:** Approved intent document (`status: approved`)  
**Output:** Implementation

The AI agent generates an implementation from the intent document combined with a project-level configuration document. The intent document captures behavior — what the unit does, its contracts, its constraints. The project config captures environment — target language and framework, coding standards, repo layout conventions, shared dependencies. These are legitimately project-wide concerns that should not be repeated in every intent document.

See [`templates/project-config.md`](../templates/project-config.md) for the project config template. Any instruction that applies to all code generation in the project belongs there; any instruction specific to this unit's behavior belongs in the intent document.

**The generated code is read-only.** If a developer identifies a problem in the implementation, the correct response is to update the intent document and regenerate — not to edit the code directly. Manual edits break the chain: the code is no longer derived from the intent, the intent no longer reflects the implementation, and the compliance check becomes meaningless.

This is enforced mechanically rather than by convention. A `PreToolUse` hook blocks an agent's attempt to edit a file inside a generated-code root and returns the correct action — update the intent document and regenerate — at the moment the incorrect one is attempted. See [`hooks/`](../hooks/) for the implementation, the Stage 6 escape hatch that lets the generation run itself write, and an honest account of what the hook does not catch. The durable backstop is the CI gate described in [`ci-cd-integration.md`](ci-cd-integration.md); the hook catches the mistake where it is cheapest to correct, CI catches whatever reaches the merge boundary.

**Exit gate:** Implementation produced. No manual edits applied.

---

### Stage 7 · Compliance Check

**Actor:** Compliance Agent  
**Input:** Approved intent document + generated implementation  
**Output:** Compliance report — pass/fail per behavioral contract item, invariant, and quality attribute threshold

The Compliance Agent verifies the implementation against the intent document independently of test results. Tests written by the AI can confirm the AI's interpretation of the intent — they cannot confirm the intent was correctly captured. The Compliance Agent breaks this circularity by checking the implementation against the source of truth directly.

If the compliance check fails, the implementation is regenerated (returning to Stage 6). Compliance failures do not trigger intent document updates unless the failure reveals a gap in the intent itself — in that case, the document returns to Stage 1 via the Intent Maintenance Agent. The engineer who approved the intent document at Stage 5 is the decision-maker for whether a compliance failure is an implementation defect (regenerate) or an intent gap (update the document and re-enter the workflow).

**Exit gate:** All behavioral contracts satisfied. All invariants hold. All quality attribute thresholds met or exceeded.

See [`workflow/ci-cd-integration.md`](ci-cd-integration.md) for how to run the compliance check as a CI gate and integrate intent document status with branch protection rules.

---

### Stage 8 · Security Audit

**Actor:** Security Agent  
**Input:** Approved intent document + generated implementation  
**Output:** Security audit report — vulnerability findings and unverifiable items

The Security Agent performs an adversarial audit of the generated implementation, checking for vulnerability classes that the Compliance Agent does not cover. The Compliance Agent verifies that the code matches what the intent document declares. The Security Agent checks for security properties that may not be declared — injection surfaces, authentication gaps, sensitive data exposure, cryptographic weaknesses, and other patterns from a standard security checklist.

This stage catches two distinct problems. First, intent gaps: the implementation correctly reflects the intent document, but the intent document failed to specify a security requirement. These findings route back to the intent document via the Intent Maintenance Agent — the security property is added to the intent, and the code is regenerated. Second, implementation defects: the intent document specifies a security requirement but the generated code violates it. These findings route directly to regeneration.

**Finding types:**
- `VULNERABILITY` — a statically detectable security defect; blocks completion; routes to intent update + regeneration (if intent gap) or regeneration (if implementation defect)
- `UNVERIFIABLE` — requires runtime testing, fuzzing, or penetration testing to confirm; does not block completion; documented for pre-production verification

**On model selection:** This stage benefits from models with security research specialization. See [`agents/README.md`](../agents/README.md#a-note-on-model-selection-for-the-security-agent) for guidance.

**Exit gate:** No `VULNERABILITY` findings. `UNVERIFIABLE` items documented and assigned for runtime verification.

---

## Handling Changes

When a change is requested after an intent document has reached `approved` or later:

1. The **Intent Maintenance Agent** is invoked first. It updates the intent document and flags conflicts with existing intent.
2. The updated document re-enters the workflow at the appropriate stage (at minimum, Stage 5 · Engineering Review for any substantive change).
3. `status` reverts to `draft` on any edit.
4. Code is regenerated from the updated intent — existing implementation is discarded.

The intent document is always updated before any code changes. There is no path by which the implementation changes without the intent document changing first.

---

## Status Lifecycle

| Status | Meaning | Code generation permitted? |
|---|---|---|
| `draft` | Work in progress | No |
| `review` | Stakeholder approved, awaiting engineering sign-off | No |
| `approved` | Engineering approved, ready for generation | Yes |
| `deprecated` | Superseded or removed | No (legacy code only) |

---

## Review Seams

The workflow has three deliberate human checkpoints, each closing a different gap:

| Seam | Stage | Actor | Gap closed |
|---|---|---|---|
| Business → Engineering | Stage 4 | Business stakeholder | Does the spec reflect the business need? |
| Engineering → AI | Stage 5 | Engineer | Is the spec precise enough to implement correctly? |
| Implementation → Reality | Post-deploy | Human tester | Does the running system serve the actual human need? |

The first two seams are internal to the workflow and gate whether generation proceeds. The third is external — it happens after deployment and is not automated.

**Who counts as a tester:** "Human tester" here refers to any person who exercises the final software with evaluative intent — not a role title or organizational function. This includes dedicated QA teams, end users evaluating the software before adoption, contractors providing testing services, or any stakeholder who has occasion to use the product. The defining characteristic is that they are assessing whether the software serves the actual need. What they surface is either a deficiency in the intent (something the spec should have said but didn't) or a refinement (something the spec got right but could be better). Both re-enter the workflow as change requests to the Intent Maintenance Agent.

**Compliance Agent vs human tester:** The Compliance Agent at Stage 7 closes the implementation/spec gap: it verifies that the generated code does what the intent document says. Human testers close a different gap: they verify that what the spec says is what users actually need. A system can pass compliance and fail human evaluation. When it does, the correct response is to update the intent document — not the code — and re-enter the workflow via the Intent Maintenance Agent.

Separating these concerns is intentional. A business stakeholder should not evaluate technical precision. An engineer should not validate business intent. A compliance agent cannot evaluate whether the spec captured the right need. Conflating any of these produces reviews that satisfy none of the concerns.

---

## Methodology Scope

The elicitation and review stages surface gaps that are detectable from the intent document. They cannot surface requirements the author did not know to include — things absent because they were never articulated, not because they were articulated poorly.

This class of gap — unknown unknowns — is only caught by human evaluation of running software. It is why the third review seam exists and why it cannot be automated: the gap becomes visible only when a person uses the system and finds it lacking.

When this happens, the finding re-enters the workflow as a change request to the Intent Maintenance Agent. The intent document is updated before any code changes — the same rule that applies to all changes.

The implication: intent documents will always be incomplete in ways that cannot be predicted in advance. The goal of elicitation and agent review is not theoretical completeness — it is to minimize the gaps catchable before generation, so that what remains are the genuinely novel gaps that only emerge from use.
