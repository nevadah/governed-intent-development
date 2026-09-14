# Governed Intent Development

A methodology for treating human intent as the source of truth in software development, with generated code as a downstream artifact.

---

## The core idea

In most projects, source code is the source of truth. Documentation, if it exists, describes the code. Tests verify what the code does. When something changes, the code changes first and everything else follows.

Specifications play a role, of course, and in a disciplined organization the spec is updated and the code is changed in response. However, while the specification informs the code, it has historically been written for human consumption, and the engineers then make changes based on their understanding of the spec.

This methodology inverts that. Source code is treated as a build artifact that is analogous to a compiled binary or a Docker image and generated from something more fundamental: a structured, versioned, human-authored description of intent. The intent document is the source of truth. Code is generated from it. The code is never manually edited; doing so is equivalent to patching a compiled binary. In other words, this document acts as a specification authored by humans, but intended for consumption by an AI directly.

---

## A note on this project

This repository is a conceptual exploration, not a production tool. At least for now.

It emerged from a conversation about where AI-assisted development is heading. Specifically, it was about what it would mean to treat human intent as the source of truth in software development, rather than source code. The documents here are an attempt to give that idea concrete form: a document format, a governed workflow, a set of agent roles. They are meant to be thought-provoking and useful as a starting point, not complete or battle-tested.

The conversation was sparked by a post on LinkedIn from Jim Honeycutt: https://www.linkedin.com/posts/jimhoneycutt_code-is-no-longer-the-source-of-truth-it-activity-7450305910834454529-FnjW/. The discussion in the comments for that post is robust and worth reviewing.

Several more developed projects are working in adjacent territory: GitHub's Spec Kit, AWS Kiro, Tessl, and others referenced in the related work section below. This project is not a competitor to those efforts. It is an independent exploration of the same underlying shift, with a particular focus on the governance and verification side of the problem. When this was first written, that focus was a genuine gap in the available tooling. It is less of one now — Spec Kit and Kiro have both added governance and verification since — and the related work section below says so plainly rather than restating a distinction that has expired.

If you are looking for a production-ready spec-driven development tool, the projects listed above are further along. If you are interested in the ideas here, what Governed Intent Development could look like with a fully governed pipeline, independent compliance verification, and a formal document format, then this project is meant for you. Critique, contributions, and real-world experiments that stress-test these ideas are exactly what this project needs to mature.

One further note: this repository was developed primarily through Claude Code, Anthropic's AI development tool, working from the author's direction and decisions. The format, workflow, agent prompts, and examples here are substantially AI-produced artifacts shaped by human intent. Whether that makes this project a live demonstration of its own premise, or simply an irony, is left to the reader — but it seemed worth stating plainly.

---

## The problem

Current AI coding tools have three structural problems:

**1. Intent evaporates.** When a session ends, the reasoning behind the code disappears. The next session starts from the code, not from why the code is what it is.

Agent memory has narrowed this problem since it was first stated — Claude Code and comparable tools now persist learnings across sessions — but it has not closed it, and the distinction matters. What memory retains is what the *agent* inferred: unversioned, unreviewed, invisible to stakeholders, and scoped to one machine or workspace. It is a cache of the assistant's working knowledge. The record a business actually needs to preserve — what was decided, by whom, and which alternatives were rejected — is not something that should live in a store nobody reviews and no one signed off on.

**2. Iteration happens at the wrong level.** When requirements change, AI tools generate new code. But the intent was never captured, so there's nothing to update. The new code reflects the new conversation, not a versioned record of what changed and why.

**3. Ambiguity is invisible.** AI tools accept natural language and generate confident implementations. When the language is ambiguous, the model makes a silent interpretive choice. Nobody agreed to it; it just becomes the code.

---

## The solution

Three components, working together:

### 1. Structured intent documents

A formal document format that captures intent precisely enough for an AI to implement correctly, and richly enough to serve as the lasting record of what was built and why.

An intent document contains:
- **Behavioral contracts** — inputs, outputs, pre/postconditions, invariants, and Given/When/Then scenarios in Gherkin
- **Domain semantics** — what the concepts mean in this domain, not just technical descriptions
- **Quality attributes** — performance thresholds, security constraints, failure modes
- **Dependencies and boundaries** — what this unit relies on, exposes, and must never know about
- **Rationale** — why decisions were made and what alternatives were rejected

See [`templates/intent-document.md`](templates/intent-document.md) for the blank template and [`schema/intent-document.schema.json`](schema/intent-document.schema.json) for the machine-readable frontmatter schema. See [`examples/intent-password-reset.md`](examples/intent-password-reset.md) for a complete worked example.

### 2. A governed workflow

A staged lifecycle analogous to Gitflow, with explicit gates between stages. Intent is authored and reviewed before code generation begins. Two distinct human review seams catch different classes of error:

- **Business stakeholder review** — is this what the business needs?
- **Engineering review** — is this precise enough for the AI to implement correctly?

Neither review touches generated code. Review happens at the intent level, upstream of implementation.

See [`workflow/workflow.md`](workflow/workflow.md) for the full stage-by-stage definition with entry/exit gates.

### 3. An agent pipeline

Four AI agents enforce and assist the process:

| Agent | Stage | Role |
|---|---|---|
| **Elicitation Agent** | After authoring | Interviews the draft document, flags ambiguities, underspecified edge cases, and missing coverage — including security-specific gaps |
| **Intent Review Agent** | After elicitation | Stress-tests the document for internal contradictions, impossible postconditions, and boundary violations |
| **Compliance Agent** | After code generation | Verifies the implementation satisfies the intent document independently of the test suite |
| **Security Agent** | After compliance | Performs an adversarial security audit of the generated code, finding vulnerability classes not covered by the compliance check |
| **Intent Maintenance Agent** | Before any change | Ensures the intent document is updated before code changes; flags breaking changes and conflicts |

See [`agents/`](agents/) for each agent, packaged as a Claude Code subagent with scoped tool access. Four of the five cannot write anything — a compliance agent that can edit the code it is judging is not an independent check, so the constraint is expressed in configuration rather than left to the prompt.

---

## Granularity: what one intent document covers

One intent document should represent one independently deployable or testable unit of behavior. In practice this means authoring at the **feature or capability level**:

- **Too narrow (function level):** An intent document per function produces hundreds of documents for a single feature, most of which have trivial behavioral contracts and no meaningful domain semantics. The overhead exceeds the benefit.
- **Too broad (service level):** An intent document per service cannot be implemented atomically and produces a behavioral contract too large for an agent to implement correctly in one pass. It also makes the compliance check intractable.
- **Right scope (feature / capability level):** A unit that can be specified, generated, and verified independently. One user-facing capability, one background job, one integration boundary, one domain operation.

A useful heuristic: if you cannot describe the unit's complete behavior in the Scenarios section without it becoming unwieldy, the unit is probably too large and should be split.

**A note on context budgets.** This guidance was first written when fitting a document, its generated unit, and a verification pass into a single context was a real constraint. It is not one now. Frontier models run million-token context windows with six-figure output limits, and a feature-scoped unit fits comfortably inside one with room for the compliance check. The heuristic above is therefore conservative rather than aspirational, and a larger unit is defensible if it is genuinely atomic. What now bounds unit size is the cost of regenerating it and a reviewer's ability to hold it in their head — not the model's capacity.

---

## Where intent documents live

Intent documents belong in an `intent/` directory at the repository root, with subdirectories mirroring domain boundaries:

```
intent/
  auth/
    password-reset.md
    session-management.md
  payments/
    refund-request.md
src/                    # generated code lives here as normal
```

The relationship between an intent document and its generated code should be traceable. The recommended convention is a matching path: `intent/auth/password-reset.md` generates into `src/auth/password-reset/`. If your project structure requires a different mapping, document it in a project-level config rather than in each intent document individually.

---

## Why the Compliance Agent matters

AI tools write code and tests together. When an AI implements something incorrectly, it tends to write tests that confirm the incorrect implementation. The test suite passes; the intent was never satisfied.

The Compliance Agent breaks this circularity. It verifies the implementation against the intent document, a source of truth the AI did not produce, independently of whether the tests pass. This is the only reliable way to catch the class of error where the AI was confidently wrong about what was asked.

---

## How this differs from related work

This field has moved quickly, and several distinctions this project originally claimed no longer hold. What follows is an honest accounting as of September 2026, including the claims that have expired.

**[GitHub Spec Kit](https://github.com/github/spec-kit)** — Reached v1.0.0 in August 2026 and ships continuously. Its workflow now opens with `/speckit.constitution`, which establishes the project's governing principles, and includes `/speckit.clarify`, `/speckit.analyze`, `/speckit.checklist`, and `/speckit.converge` — the last of which assesses an existing codebase against its spec, plan, and tasks. An earlier version of this README asserted that Spec Kit defined no governed workflow and included no compliance verification step. That was true when written and is not true now. Spec Kit also integrates with 30+ coding agents, which is far broader tool support than anything proposed here.

**[AWS Kiro](https://kiro.dev)** — Generally available since May 2026, with credit-based pricing and IDE, CLI, and web surfaces. Its model pairs specs with steering files and background hooks that can run checks after a task completes or require a review step before certain actions. It has since added organization-level governance: security policies enforced fleet-wide, per-user telemetry export, and compliance certification. The distinction worth drawing is that Kiro's governance is largely operational — who may do what, and what gets recorded — where this project's is semantic: is the implementation faithful to the stated intent?

**MindStudio Remy** — Previously listed here as "generation without governance." That was a miscategorization. Remy holds explicitly that the spec remains the source of truth as models improve, which is the same position this project takes. It is a peer, not a contrast.

**[Tessl](https://tessl.io)** — The closest parallel to this project's premise: a spec-centric framework plus a public spec registry, distinguishing spec-produces-code from code-produces-spec as separate operations. Substantially better funded and further along, though the framework was still in limited release as of mid-2026.

**Other work in the space** — BMAD-METHOD (open-source, multi-persona agent workflow), OpenSpec (a propose/implement/archive command model now used as an academic baseline), Google Antigravity (which publishes official spec-driven codelabs, including one combining it with Spec Kit), and Traycer (a commercial plan/execute/verify layer).

**Change Intent Records (CIRs)** — Lightweight records of why a change was made, analogous to ADRs. Useful for the rationale layer of an intent document, but not a full methodology. No workflow, no agents, no behavioral contracts.

**Intent-Driven Development (IDD)** — The term is in use across several contexts, generally meaning "start with intent before writing code." Governed Intent Development is a specific instance of this principle. The "governed" qualifier is the distinguishing characteristic: a formal document format with an enforced lifecycle, staged workflow gates, and an agent pipeline that closes the loop between intent and implementation. Looser interpretations of "intent-driven" share the starting point but not the structure.

### What is actually distinctive

Stripped of the claims that have expired, four things remain:

1. **Generated code is read-only, and enforced as such.** No other tool surveyed asserts this. Spec Kit and Kiro are spec-*first*: the spec drives generation, but once code exists it is editable and authoritative. This project treats a hand-edit as equivalent to patching a compiled binary, and ships a [`PreToolUse` hook](hooks/) that blocks the edit rather than asking an agent not to make it.
2. **Compliance verification independent of the test suite.** `/speckit.converge` assesses code against spec, which is close. The difference is the premise: the Compliance Agent exists specifically because an AI that implements something incorrectly will write tests that confirm the incorrect implementation, so a passing suite is not evidence.
3. **Two distinct human review seams.** Business review and engineering review ask different questions and are deliberately not performed by the same person. Most tools have one review step, or none.
4. **A separate adversarial security stage.** Compliance asks whether the code matches what the document declared. Security asks about the properties the document failed to declare. Conflating them means the second question never gets asked.

**On the name:** "Governed Intent Development" was chosen to distinguish this methodology from the broader intent-driven development concept and to surface its defining characteristic — the governance layer. It may change as the methodology matures.

---

## Known objections

This methodology sits at the far end of the spec-driven spectrum, and that end is contested. Birgitta Böckeler's [taxonomy for Thoughtworks](https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) distinguishes three levels: *spec-first* (the spec drives initial generation, then the code takes over), *spec-anchored* (spec and code are maintained in step), and *spec-as-source* (humans edit only the spec; generated code is never touched). Governed Intent Development is squarely spec-as-source, and it is worth stating plainly that this is the least-proven of the three.

Anyone evaluating this methodology should weigh the following objections. They are presented as they are argued, not as strawmen.

**"This is Model-Driven Development again."** The most common rebuttal, and not a cheap one — MDD made a structurally identical bet and largely failed. The strongest counterargument is that MDD's generators demanded a complete, formal model, while an LLM tolerates prose and fills the gaps. But that cuts both ways: an LLM filling gaps silently is precisely the failure the Elicitation Agent exists to prevent, and this project has not been tested at a scale where the comparison could be settled. Treat it as an open question.

**"You can't specify everything up front."** Kent Beck's version, [quoted by Martin Fowler](https://martinfowler.com/fragments/2026-01-08.html): writing the whole specification before implementation "encodes the (to me bizarre) assumption that you aren't going to learn anything during implementation that would change the specification." This is correct, and the workflow is built to concede it. The third review seam — a human exercising running software — exists because some requirements are only discoverable from use, and the workflow's Methodology Scope section says so directly. What the methodology insists on is not that learning stops, but that learning is written back into the intent document instead of into the code.

**"Specs drift from code within days."** The recurring practical complaint: an agent hits an undocumented constraint mid-implementation, resolves it inline, and the document is stale immediately. The Intent Maintenance Agent and the read-only rule are the answer, and they are worth exactly as much as their enforcement — a methodology that relies on discipline alone to prevent drift will drift. This is the objection that motivated [`hooks/`](hooks/), which blocks the inline fix at the moment it is attempted rather than asking for restraint. The hook is not total, and its limits are documented rather than glossed.

**"Reviewing markdown is worse than reviewing code."** Review fatigue moves upstream rather than disappearing, and a long intent document can be rubber-stamped as easily as a long diff. Partially conceded. The mitigation worth adopting is risk tiering: not every unit warrants all five agent gates, and forcing the full pipeline onto trivial changes is an efficient way to make reviewers stop reading.

**"The economics don't work."** The clearest public datapoint for an organization running a comparable model is on the order of $1,000/day per engineer in tokens. Regenerating a unit is inherently more expensive than the edit it replaces. Anyone adopting this should price it first.

### What the evidence supports

One finding runs in this project's favor. A [2026 study of citation discipline in spec-driven development](https://arxiv.org/abs/2606.30689) found that requiring generated code to cite the specific requirement it implements enables automated hallucination detection at roughly 86–88% true-positive with no false positives, while uncited conditions were undetectable. That is direct support for the traceability premise underlying the Compliance Agent. The same study found that citation discipline measurably *reduces* output determinism — a real cost, noted here rather than omitted.

The most serious real-world test of the strong form of this thesis is StrongDM's engineering organization, [documented by Simon Willison](https://simonwillison.net/2026/Feb/7/software-factory/), which operates under explicit rules that code must not be written by humans and must not be reviewed by humans. Their verification approach is worth studying: end-to-end scenarios are held outside the codebase as a holdout set, on the reasoning that an agent with access to its own tests will write tests that pass. That is a sharper answer to "how do you verify without reading the code" than anything currently in this repo's workflow.

---

## What's in this repo

```
schema/                         # JSON Schema for intent document frontmatter
  intent-document.schema.json

templates/                      # Blank template for authoring intent documents
  intent-document.md

examples/                       # Worked examples
  intent-password-reset.md      # Complete example: email-based password reset

workflow/                       # The governed workflow
  workflow.md                   # Stage definitions, gates, and handoffs

agents/                         # The five pipeline agents, as Claude Code subagents
  elicitation-agent.md
  review-agent.md
  compliance-agent.md
  security-agent.md
  maintenance-agent.md

hooks/                          # Mechanical enforcement of the read-only rule
  protect_generated_code.py     # PreToolUse hook blocking edits to generated code

.claude-plugin/                 # Makes the repo installable as a Claude Code plugin
```

---

## Installing it

The agents and the enforcement hook install together:

```
/plugin marketplace add nevadah/governed-intent-development
/plugin install governed-intent@governed-intent-development
```

Everything here also works without the plugin. The agent files are self-contained system prompts usable in any tool that accepts one, the hook is a standalone script, and the template, schema and workflow are just documents.

---

## Status

Early-stage. The format, workflow, and agent prompts are a first version. They are usable, but expected to evolve as they are applied to real projects. Open questions include the right granularity for intent documents, how breaking changes to intent propagate through a dependency graph, and how this integrates with existing CI/CD tooling.

Contributions and feedback welcome.
