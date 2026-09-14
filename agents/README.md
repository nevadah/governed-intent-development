# Agents

The five agents in the Governed Intent Development pipeline. Each file is a Claude Code subagent: YAML frontmatter declaring its name, when to use it, and which tools it may touch, followed by the system prompt itself.

| Agent | File | Workflow stage | Tools |
|---|---|---|---|
| Intent Elicitation Agent | [elicitation-agent.md](elicitation-agent.md) | Stage 2 — after authoring | read-only |
| Intent Review Agent | [review-agent.md](review-agent.md) | Stage 3 — after elicitation | read-only |
| Compliance Agent | [compliance-agent.md](compliance-agent.md) | Stage 7 — after code generation | read-only |
| Security Agent | [security-agent.md](security-agent.md) | Stage 8 — after compliance check | read-only |
| Intent Maintenance Agent | [maintenance-agent.md](maintenance-agent.md) | Pre-change gate — before any revision | read + write |

See [workflow/workflow.md](../workflow/workflow.md) for where each agent fits in the full lifecycle.

---

## Why the tool scoping matters

Four of the five agents cannot write anything. That is not a precaution, it is the methodology expressed in configuration.

The Security Agent's prompt insists that a finding must never be a patch — "parameterize this query on line 47" is the wrong output, because security findings route back to the intent document and the code changes only through regeneration. Denying it `Edit` and `Write` means that rule no longer depends on the model honoring its instructions. The same argument applies to the Compliance Agent, whose entire value is that it is an independent observer: an observer that can edit the thing it is judging is not independent.

The Intent Maintenance Agent is the one that writes, because producing an updated intent document is its output. It writes documents, not code — and the [read-only hook](../hooks/) stops it reaching generated code even if it tries.

---

## Using them

**In Claude Code.** Copy this directory to `.claude/agents/` in your project, or install the whole methodology as a plugin:

```
/plugin marketplace add nevadah/governed-intent-development
/plugin install governed-intent@governed-intent-development
```

Then invoke a stage by asking for it — "use the elicitation agent on intent/auth/password-reset.md" — or let Claude select the agent from its description.

**In CI or another tool.** Everything below the frontmatter is a self-contained system prompt and works anywhere you can set one, including headless runs. See [workflow/ci-cd-integration.md](../workflow/ci-cd-integration.md) for running the compliance and security agents as merge gates.

---

## A note on model selection for the Security Agent

The Security Agent performs an adversarial audit designed to find vulnerability classes that general-purpose code generation misses. This stage benefits significantly from models with security research specialization. If your organization has access to a model specifically evaluated on vulnerability detection or security research tasks, use it here rather than the same general-purpose model that produced the code. A general-purpose model can fulfill this role, but may share the blind spots of the model that wrote the implementation — a security-specialized model is explicitly oriented toward finding what generation leaves behind.

The Compliance and Security agents declare `model: opus` for the same reason: the stages that exist to catch what generation got wrong should not be the cheapest link in the chain.
