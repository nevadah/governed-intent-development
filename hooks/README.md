# Enforcement Hooks

The methodology's load-bearing constraint is that generated code is never hand-edited. Until now that constraint was stated and not enforced: [`workflow/workflow.md`](../workflow/workflow.md) has a "Manual edits attempted? → STOP" branch with nothing behind it, and a rule that depends on discipline is a rule that erodes.

This directory contains the mechanism.

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
GID_GENERATING=1 claude -p "Generate the implementation for intent/auth/password-reset.md"
```

This is the honest seam in the design. The hook cannot distinguish a generation run from a developer who set the variable to get their edit through, so the escape hatch is process, not mechanism. What it buys is that bypassing the rule is now a deliberate act that appears in shell history and CI configuration, rather than a silent edit that looks like any other commit. Make the variable's use visible: set it in the generation script, never in a shell profile.

---

## What this does not catch

Stated plainly, because a partial control that is believed to be total is worse than no control:

- **Shell writes.** The hook inspects `file_path` on file-editing tools. An agent running `echo x > src/f.py` through `Bash` is not intercepted. Blocking that reliably means parsing arbitrary shell, which is not a thing this hook attempts.
- **Edits outside the agent.** A developer opening the file in an editor is unaffected. The hook governs agent behavior, not human behavior.
- **Other agents.** This is Claude Code's hook protocol. Another tool needs its own equivalent.

The durable backstop for all three is CI, not the hook: a check that every implementation file changed in a pull request has a corresponding intent document in `approved` status, and that the compliance agent passes against it. The hook catches the mistake at the moment it is made, in the loop where it is cheapest to correct. CI catches what reaches the merge boundary regardless of how it got there. See [`workflow/ci-cd-integration.md`](../workflow/ci-cd-integration.md).
