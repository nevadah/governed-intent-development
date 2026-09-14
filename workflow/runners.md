# Gate Runners

The compliance and security gates are prompts, a set of files to read, and a verdict to parse. Nothing about them requires a particular vendor. [`scripts/run_intent_gate.py`](../scripts/run_intent_gate.py) can drive them through any agent CLI.

What *is* required is that the agent cannot modify the code it is judging. The whole argument for the Compliance Agent is that it is an independent observer, and an observer that can edit the thing it observes is not independent. That property has to come from the tool, not from the prompt — asking a model not to write files is not the same as it being unable to.

So each runner declares what it can actually guarantee, and the gate refuses to run on anything weaker unless you explicitly accept the downgrade.

---

## Where each runner stands

Claims below were checked against first-party documentation on **2026-09-14**. Agent CLIs change quickly; re-check before relying on any of this.

| Runner | Read-only | Basis |
|---|---|---|
| `claude` | **enforced** | `--allowedTools Read,Grep,Glob` restricts the toolset at the harness level. The repo's [`PreToolUse` hook](../hooks/) is a second layer. |
| `codex` | **enforced** | `--sandbox read-only` is documented as "read files but cannot write anything or run commands." |
| `gemini` | **unverified** | `--allowed-tools` is deprecated in favour of a Policy Engine we have not evaluated. No documented mechanism was confirmed either way. |
| `custom` | **advisory** | An arbitrary command. We know nothing about it. |

Only `enforced` runs by default. Anything else requires `--allow-unenforced-read-only`, which appends a written instruction not to modify files, labels the CI job summary accordingly, and leaves the gate's independence resting on the model's cooperation.

This is deliberately annoying. A governance tool that silently degrades its own guarantee to be more convenient is worse than one that makes you say out loud that you are degrading it.

```bash
python scripts/run_intent_gate.py --list-runners
```

---

## Per-runner notes

### claude

```bash
python scripts/run_intent_gate.py compliance \
    --intent intent/auth/password-reset.md \
    --implementation src/auth/password-reset
```

The default. Takes the system prompt on the command line with `--append-system-prompt`, so the agent definition is passed through unmodified. `ANTHROPIC_API_KEY`.

### codex

```bash
python scripts/run_intent_gate.py compliance --runner codex \
    --intent intent/auth/password-reset.md \
    --implementation src/auth/password-reset
```

Three things to know:

- **No system-prompt flag.** Codex has no documented equivalent of `--append-system-prompt`, so the agent definition and the task are concatenated and piped to `codex exec -`. This is a real semantic difference: the agent's instructions arrive as user input rather than as a system prompt. In practice the reports come out the same, but it is not the identical mechanism.
- **`AGENTS.md` may load automatically.** Codex originated that convention. If it does, this repo's `AGENTS.md` silently joins the gate's context. That is probably harmless and possibly useful, but it is not something the gate controls.
- **`CODEX_API_KEY`**, per the non-interactive docs — not `OPENAI_API_KEY`. Verify before assuming the older variable works.

We mark Codex `enforced` on the strength of the documented meaning of `--sandbox read-only`. We have not independently verified the underlying OS-level sandbox mechanism.

### gemini

```bash
python scripts/run_intent_gate.py compliance --runner gemini \
    --allow-unenforced-read-only \
    --intent intent/auth/password-reset.md \
    --implementation src/auth/password-reset
```

Requires the downgrade flag, for a specific reason: the command-line tool restriction (`--allowed-tools`) is deprecated in favour of a config-based Policy Engine, and we have not established whether that engine can prevent file writes. This may well be a documentation gap on our side rather than a real limitation. If you determine otherwise, that is a one-line change to `RUNNERS` in the script and a correction here.

The system prompt is piped on stdin and the task passed with `-p`, which the CLI appends to stdin input. The API key environment variable is not documented in the CLI reference we checked.

### custom

```bash
python scripts/run_intent_gate.py compliance --runner custom \
    --command "mytool run --prompt {task}" \
    --allow-unenforced-read-only \
    --intent intent/auth/password-reset.md \
    --implementation src/auth/password-reset
```

`{task}` and `{system_prompt}` are substituted as whole arguments — never string-formatted, so braces inside a prompt cannot be mistaken for placeholders. Always advisory, because we cannot reason about a command we have never seen.

---

## Not evaluated

GitHub Copilot CLI, Cursor's headless agent, Amp, Aider, opencode, goose, and Qwen Code were not investigated. Their absence from the table means nobody has checked, not that they are unsuitable. `--runner custom` will drive any of them today, at advisory level.

---

## Adding a runner

Add an entry to `RUNNERS` in [`run_intent_gate.py`](../scripts/run_intent_gate.py) with its `argv` template, optional `stdin` template, key environment variable, and honest `read_only` level. Add a row above with the source you checked and the date. The tests assert that every runner declares a level, so a new entry cannot skip the question.

The bar for claiming `enforced`: first-party documentation stating the agent cannot write files. Not a sandbox flag that sounds restrictive, not a tool-allowlist that might be advisory, and not an assumption that a vendor surely handles this. If the documentation does not say it, the honest answer is `unverified`, and `unverified` is a perfectly respectable thing for this table to say.
