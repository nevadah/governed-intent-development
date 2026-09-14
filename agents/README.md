# Agents

The five agents in the Governed Intent Development pipeline. Each file is a self-contained system prompt, preceded by a few lines of YAML frontmatter declaring the agent's name, when to use it, and which tools it may touch.

The prompt is the substance and works anywhere you can set one. The frontmatter is additive: Claude Code reads it to register the file as a subagent, other tools ignore it, and [`scripts/run_intent_gate.py`](../scripts/run_intent_gate.py) strips it when driving the agent through a CLI.

| Agent | File | Workflow stage | Needs to write? |
|---|---|---|---|
| Intent Elicitation Agent | [elicitation-agent.md](elicitation-agent.md) | Stage 2 — after authoring | No |
| Intent Review Agent | [review-agent.md](review-agent.md) | Stage 3 — after elicitation | No |
| Compliance Agent | [compliance-agent.md](compliance-agent.md) | Stage 7 — after code generation | No |
| Security Agent | [security-agent.md](security-agent.md) | Stage 8 — after compliance check | No |
| Intent Maintenance Agent | [maintenance-agent.md](maintenance-agent.md) | Pre-change gate — before any revision | Yes — intent documents only |

See [workflow/workflow.md](../workflow/workflow.md) for where each agent fits in the full lifecycle.

---

## Why the tool scoping matters

Four of the five agents cannot write anything. That is not a precaution, it is the methodology expressed in configuration.

The Security Agent's prompt insists that a finding must never be a patch — "parameterize this query on line 47" is the wrong output, because security findings route back to the intent document and the code changes only through regeneration. Denying it `Edit` and `Write` means that rule no longer depends on the model honoring its instructions. The same argument applies to the Compliance Agent, whose entire value is that it is an independent observer: an observer that can edit the thing it is judging is not independent.

The Intent Maintenance Agent is the one that writes, because producing an updated intent document is its output. It writes documents, not code — and where the [read-only hook](../hooks/) is available, it is stopped from reaching generated code even if it tries.

Whether the restriction is *enforced* or merely *stated* depends on the tool. That difference is tracked rather than assumed: see [`workflow/runners.md`](../workflow/runners.md).

---

## Using them

**In any tool.** Everything below the frontmatter is a system prompt. Paste it into a chat, set it as a custom instruction, or hand it to a CLI. Nothing in these prompts assumes a particular vendor, and the report formats they specify are plain markdown.

**As a CI gate.** [`scripts/run_intent_gate.py`](../scripts/run_intent_gate.py) drives the compliance and security agents headlessly through Claude Code, Codex, Gemini, or a command of your own, reading the prompt from these files so the gate and the interactive agent cannot drift apart. See [workflow/ci-cd-integration.md](../workflow/ci-cd-integration.md) and [workflow/runners.md](../workflow/runners.md).

**In Claude Code.** The frontmatter makes each file a subagent. Copy this directory to `.claude/agents/`, or install the whole methodology in one step:

```
/plugin marketplace add nevadah/governed-intent-development
/plugin install governed-intent@governed-intent-development
```

Then invoke a stage by asking for it — "use the elicitation agent on intent/auth/password-reset.md" — or let the tool select the agent from its description.

---

## A note on model selection for the Security Agent

The Security Agent performs an adversarial audit designed to find vulnerability classes that general-purpose code generation misses. This stage benefits significantly from models with security research specialization. If your organization has access to a model specifically evaluated on vulnerability detection or security research tasks, use it here rather than the same general-purpose model that produced the code. A general-purpose model can fulfill this role, but may share the blind spots of the model that wrote the implementation — a security-specialized model is explicitly oriented toward finding what generation leaves behind.

The Compliance and Security agents declare `model: opus` for the same reason: the stages that exist to catch what generation got wrong should not be the cheapest link in the chain.
