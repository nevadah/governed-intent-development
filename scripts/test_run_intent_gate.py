#!/usr/bin/env python3
"""Tests for the intent gate runner.

Run: python scripts/test_run_intent_gate.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_intent_gate import (
    AGENTS,
    RUNNERS,
    build_invocation,
    parse_result,
    resolve_runner,
    strip_frontmatter,
    substitute,
)


def main():
    failures = []

    def check(name, condition):
        if condition:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name}")
            failures.append(name)

    body = strip_frontmatter("---\nname: x\ntools: Read\n---\n\nYou are the agent.\n")
    check("strips subagent frontmatter", body == "You are the agent.\n")
    check("leaves a body with no frontmatter alone", strip_frontmatter("You are.") == "You are.")

    check("parses PASS", parse_result("**Result:** PASS\n") == "PASS")
    check("parses FAIL", parse_result("**Document:** x\n**Result:** FAIL\n") == "FAIL")
    check("parses FINDINGS", parse_result("**Result:** FINDINGS") == "FINDINGS")
    check(
        "ignores the format template line",
        parse_result("**Result:** PASS | FAIL\n\n**Result:** FAIL") == "FAIL",
    )
    check("returns None with no result line", parse_result("no verdict here") is None)

    check(
        "substitutes whole tokens only",
        substitute(["a", "{task}", "b"], {"{task}": "T"}) == ["a", "T", "b"],
    )
    check(
        "leaves braces inside a value uninterpreted",
        substitute(["{task}"], {"{task}": "interface{} and {system_prompt}"})
        == ["interface{} and {system_prompt}"],
    )

    os.chdir(Path(__file__).resolve().parent.parent)

    for gate, agent in AGENTS.items():
        prompt = Path(agent["prompt"])
        check(f"{gate} agent prompt exists", prompt.exists())
        check(
            f"{gate} agent prompt survives frontmatter stripping",
            len(strip_frontmatter(prompt.read_text(encoding="utf-8"))) > 500,
        )

    argv, stdin_text = build_invocation(AGENTS["compliance"], RUNNERS["claude"], "intent/a.md", "src/a", None)
    check("claude passes read-only tools", "Read,Grep,Glob" in argv)
    check("claude grants no write tools", not any("Edit" in part for part in argv))
    check("claude needs no stdin", stdin_text is None)
    check("names the intent document in the task", any("intent/a.md" in part for part in argv))

    argv, _ = build_invocation(AGENTS["security"], RUNNERS["claude"], "intent/a.md", "src/a", "opus")
    check("forwards a model override", "--model" in argv and "opus" in argv)

    argv, stdin_text = build_invocation(AGENTS["compliance"], RUNNERS["codex"], "intent/a.md", "src/a", None)
    check("codex runs the read-only sandbox", "--sandbox" in argv and "read-only" in argv)
    check("codex reads its prompt from stdin", argv[:3] == ["codex", "exec", "-"])
    check("codex stdin carries both prompt and task", "intent/a.md" in stdin_text and "Compliance Agent" in stdin_text)
    check("codex adds no model flag", "--model" not in argv)

    argv, stdin_text = build_invocation(AGENTS["compliance"], RUNNERS["gemini"], "intent/a.md", "src/a", None)
    check("gemini passes the task with -p", "-p" in argv)
    check("gemini stdin carries the system prompt", "Compliance Agent" in stdin_text)

    # Runners that cannot be shown to enforce read-only get told so in the prompt.
    check(
        "unenforced runner is warned in its system prompt",
        "Do not create, modify, or delete" in stdin_text,
    )
    _, enforced_stdin = build_invocation(AGENTS["compliance"], RUNNERS["codex"], "i.md", "s", None)
    check(
        "enforced runner gets no such warning",
        "Do not create, modify, or delete" not in enforced_stdin,
    )

    custom = resolve_runner("custom", "mytool --prompt {task}")
    check("custom runner splits its command", custom["argv"][:2] == ["mytool", "--prompt"])
    check("custom runner is advisory", custom["read_only"] == "advisory")

    try:
        resolve_runner("custom", None)
        check("custom without --command is rejected", False)
    except SystemExit:
        check("custom without --command is rejected", True)

    try:
        resolve_runner("nonesuch", None)
        check("unknown runner is rejected", False)
    except SystemExit:
        check("unknown runner is rejected", True)

    check(
        "every runner declares a read-only level",
        all(r["read_only"] in {"enforced", "unverified", "advisory"} for r in RUNNERS.values()),
    )

    print(f"\n{len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
