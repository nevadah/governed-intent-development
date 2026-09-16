# Enforcement Hooks

The methodology's load-bearing constraint is that generated code is never hand-edited. A rule that depends on discipline is a rule that erodes, so it is enforced in two places:

| Where | What it catches | Works on |
|---|---|---|
| **CI** — [`scripts/`](../scripts/) | Anything that reaches the merge boundary, however it got there | Any tool, any agent, any editor |
| **In the session** — this directory | The edit at the moment it is attempted, before it exists | Tools that let a hook veto an edit |

**If you are choosing one, choose CI.** It is portable, it cannot be argued out of its decision by the agent it is judging, and it catches human edits as well as agent edits. This hook is the fast feedback layer on top: it turns a failed build twenty minutes later into a corrected course immediately, and it tells the agent what to do instead.

This directory contains the in-session half.

---

## What it does

[`protect_generated_code.py`](protect_generated_code.py) is a `PreToolUse` hook. Before an agent's `Edit`, `Write`, `MultiEdit`, or `NotebookEdit` call executes, the hook inspects the target path. If the path is inside a generated-code root, the hook exits 2, which blocks the call and returns an explanation to the agent:

```
Blocked: src/auth/reset.py is generated code and is read-only under Governed
Intent Development.

Generated code is a build artifact. Editing it severs the chain between the
intent document and the implementation, and makes the compliance check
meaningless.

Do this instead:
  1. Identify the intent document this unit was generated from.
  2. Update that document to describe the behavior you wanted.
  3. Re-enter the workflow via the Intent Maintenance Agent and regenerate.
```

The agent receives that text and adjusts. The point is not to punish the attempt — it is that the correct action is stated at the moment the incorrect one is attempted.

Reads are never blocked. The compliance and security agents must be able to read the implementation.

---

## Installing it in your project

Copy `protect_generated_code.py` into your repository and register it in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python hooks/protect_generated_code.py"
          }
        ]
      }
    ]
  }
}
```

Then declare which paths are generated, in `.governed-intent.json` at the repository root:

```json
{
  "generated_paths": ["src/**"],
  "generation_env": "GID_GENERATING"
}
```

`generated_paths` are glob patterns matched against repository-relative paths; a pattern ending in `/**` also matches files directly inside that directory. If the file is absent, the default is `src/**`.

Verify the hook with `python hooks/test_protect_generated_code.py`.

---

## The generation escape hatch

Stage 6 needs to write the very files this hook protects. When the environment variable named by `generation_env` is set to a non-empty value, writes are allowed:

```bash
GID_GENERATING=1 <your agent> "Generate the implementation for intent/auth/password-reset.md"
```

This is the honest seam in the design. The hook cannot distinguish a generation run from a developer who set the variable to get their edit through, so the escape hatch is process, not mechanism. What it buys is that bypassing the rule is now a deliberate act that appears in shell history and CI configuration, rather than a silent edit that looks like any other commit. Make the variable's use visible: set it in the generation script, never in a shell profile.

---

## What this does not catch

Stated plainly, because a partial control that is believed to be total is worse than no control:

- **Shell writes.** The hook inspects `file_path` on file-editing tools. An agent running `echo x > src/f.py` through `Bash` is not intercepted. Blocking that reliably means parsing arbitrary shell, which is not a thing this hook attempts.
- **Edits outside the agent.** A developer opening the file in an editor is unaffected. The hook governs agent behavior, not human behavior.
- **Other agents.** This implements Claude Code's hook protocol, which is the one surveyed that lets a hook veto a tool call before it runs. Cursor's rules are documented as advisory with no mechanism to block a violation. Codex's execpolicy `.rules` files look like the most promising unexplored lead, and Copilot CLI, Amp, Aider, goose and the rest were not evaluated — their absence here means nobody checked, not that they cannot do it. A port is a welcome contribution.

The durable backstop for all three is CI, as above: [`check_intent_status.py`](../scripts/check_intent_status.py) asserts every changed unit has an approved intent document, and [`run_intent_gate.py`](../scripts/run_intent_gate.py) runs the compliance and security agents against it. Neither needs this hook, and neither cares which tool wrote the code. See [`workflow/ci-cd-integration.md`](../workflow/ci-cd-integration.md).
