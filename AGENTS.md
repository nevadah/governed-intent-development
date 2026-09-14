# Agent Instructions — governed-intent-development

Read `WORKING_STYLE.md` at session start. It contains cross-project preferences that apply here.

---

## Project

A methodology and tooling framework for treating human intent as the source of truth in software development, with generated code as a downstream artifact. This repo contains the specification, schema, templates, examples, agent definitions, and the enforcement mechanisms that make the methodology's rules mechanical rather than advisory.

There is no build and no linter. There is a small test suite covering the enforcement hook and the CI gate scripts — run it before any push:

```bash
python scripts/validate-intent.py
python scripts/test_check_intent_status.py
python scripts/test_run_intent_gate.py
python hooks/test_protect_generated_code.py
```

Quality gates from WORKING_STYLE.md also apply to documentation: audit for staleness before any push. This repo makes claims about other projects and about the state of the tooling, and those claims expire.

---

## Repo Structure

```
schema/               # JSON Schema for intent document frontmatter
templates/            # Blank templates for authors to fill in
examples/             # Worked examples demonstrating the format
workflow/             # Stage definitions, gates, dependency and CI policy
agents/               # The five pipeline agents, as Claude Code subagents
hooks/                # PreToolUse enforcement of the read-only rule
scripts/              # CI gates: schema, intent status, compliance, security
.claude-plugin/       # Plugin and marketplace manifests
```

---

## Environment Note

The `gh` CLI and `bd` (Beads) may not be on PATH in bash sessions. Prepend both before use:

```bash
export PATH="$PATH:/c/Program Files/GitHub CLI:/c/Users/Nevada/AppData/Local/Programs/bd"
```

---

## Methodology Constraints

This repo defines the methodology; it does not yet fully practise it. `examples/` demonstrates the document *format* against illustrative domains — it does not contain intent documents for this repo's own components, and the code in `hooks/` and `scripts/` was hand-written rather than generated from intent. Retrofitting those is tracked work, not a claim to make in the meantime.

What the repo must hold to: any change to the workflow, template, or schema has downstream effects on the agent definitions and the examples, and those are updated in the same change rather than deferred. A methodology repo whose own artifacts contradict each other is evidence against the methodology.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
