# Contributing to Governed Intent Development

This repo defines a methodology. Contributing means proposing changes to the methodology itself — its document format, workflow, agent prompts, or examples. This is different from contributing to a software project: the artifacts here are specifications, not code.

---

## What can be contributed

**New examples** — Worked intent documents demonstrating the format in a domain not yet covered. Examples are the most valuable contribution: they stress-test the format against real scenarios and surface gaps that abstract specification cannot.

**Proposed changes to the template or schema** — Changes to `templates/intent-document.md` or `schema/intent-document.schema.json` that improve clarity, fix ambiguity, or add a structural element that examples have shown to be necessary.

**Proposed changes to the workflow** — Changes to `workflow/workflow.md` or `workflow/dependency-propagation.md` that address a gap, correct an inconsistency, or add a missing policy. Changes to the workflow have downstream effects on the agent prompts — flag these explicitly.

**Proposed changes to agent prompts** — Changes to any file in `agents/` that improve an agent's output quality, fix a prompt that produces incorrect behavior, or add a flag type or issue type not currently covered.

**Support for another tool** — The most valuable contribution currently available. A gate runner for an agent CLI that is not yet supported (see [`workflow/runners.md`](workflow/runners.md)), a port of the read-only hook to another tool's enforcement mechanism, or a correction to a `read_only` level we have recorded wrongly. Making any part of this work somewhere new is worth more than deepening an existing integration.

**Proposed changes to the README or other documentation** — Clarifications, corrections, or additions that improve the repo's accessibility as a public resource.

---

## How to propose a change

### 1. Open an issue first

Before writing anything, open a GitHub issue describing what you want to change and why. Include:

- What the current behavior or content is
- What you propose changing it to
- Why the change improves the methodology (a real scenario where the current version falls short is the strongest argument)

For **new examples**, the issue should describe the domain and explain what the example demonstrates that existing examples do not.

For **template or schema changes**, the issue should include a before/after diff of the affected section and at least one example showing how the change affects a real intent document.

For **workflow changes**, the issue should explain which stage or gate is affected and whether the change is additive (new guidance) or corrective (fixing incorrect guidance). Changes that affect the stage lifecycle (adding a stage, removing a gate) require stronger justification and broader discussion.

### 2. Wait for discussion to settle

Methodology changes benefit from discussion before implementation. Wait for at least one response on the issue before opening a PR, unless the change is unambiguously a correction (typo, broken link, factual error).

### 3. Branch and implement

Branch from an up-to-date `main`. Use a descriptive branch name that reflects what is changing:

```
examples/order-fulfillment
workflow/add-dependency-review-stage
template/add-generated-by-field
agents/elicitation-add-concurrency-flag-type
docs/clarify-granularity-guidance
```

### 4. Open a pull request

The PR description should:

- Reference the issue it addresses
- Explain what changed and why, not just what changed
- For template or schema changes: show how at least one existing example would look with the change applied (or confirm it is unaffected)
- For workflow changes: confirm whether any agent prompt files need corresponding updates

---

## Standards for examples

A contributed example must:

- Be a complete, filled-in intent document — not a partial or placeholder
- Cover a domain not already represented in `examples/`
- Demonstrate at least one aspect of the format not prominent in existing examples (a new quality attribute pattern, a dependency boundary scenario, an unusual failure mode, etc.)
- Pass schema validation against `schema/intent-document.schema.json`
- Include scenarios in all four coverage categories: happy path, edge cases, failure modes, and security-relevant paths

A contributed example should not:

- Duplicate the structure of an existing example without adding new demonstrative value
- Use a contrived or toy domain — examples should reflect real engineering scenarios

---

## Standards for template and schema changes

Changes to the template or schema are high-impact: they affect every future intent document authored against them. The bar is higher than for examples or documentation.

A proposed change must:

- Have a corresponding issue with a clear rationale and at least one real example motivating it
- Be backward-compatible unless a breaking change is explicitly justified — existing intent documents should not be invalidated by a template update
- Update the template and schema in sync — a new frontmatter field must appear in both

---

## Standards for workflow changes

The workflow defines the governance model for the entire methodology. Changes here affect everyone who adopts it.

- Changes that add optional guidance (a note, a recommendation) are lower-friction
- Changes that alter gates (what is required to advance between stages) require strong justification and should be discussed in the issue before implementation
- Any workflow change that affects what an agent is expected to do must be accompanied by corresponding updates to the affected agent prompts in `agents/`

---

## What this repo is not the right place for

- **Product tooling** — an IDE plugin, a hosted service, or a general-purpose intent authoring application is out of scope. The repo defines the methodology.

  The boundary moved once and is worth stating precisely. Enforcement mechanisms are *in* scope: the schema validator, the read-only hook in `hooks/`, and the CI gates are part of the methodology, because a governance rule that cannot be enforced is a suggestion. If a contribution makes a stated rule mechanical, it belongs here. If it builds a product around the methodology, it does not.
- **Project-specific adaptations** — if you are adapting this methodology for a specific tech stack or domain, that belongs in your own project. Contributions here should apply broadly.
- **Debate about whether this approach is valid** — issues and PRs are for improving the methodology as defined, not for relitigating its premises.
