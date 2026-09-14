#!/usr/bin/env python3
"""Tests for the intent gate runner.

Run: python scripts/test_run_intent_gate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_intent_gate import AGENTS, build_command, parse_result, strip_frontmatter


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

    repo_root = Path(__file__).resolve().parent.parent
    for gate, agent in AGENTS.items():
        prompt = repo_root / agent["prompt"]
        check(f"{gate} agent prompt exists", prompt.exists())
        check(
            f"{gate} agent prompt survives frontmatter stripping",
            len(strip_frontmatter(prompt.read_text(encoding="utf-8"))) > 500,
        )

    import os

    os.chdir(repo_root)
    command = build_command(AGENTS["compliance"], "intent/a.md", "src/a", None)
    check("passes read-only tools", "Read,Grep,Glob" in command)
    check("does not grant write tools", not any("Edit" in part for part in command))
    check("names the intent document in the task", "intent/a.md" in command[2])

    command = build_command(AGENTS["security"], "intent/a.md", "src/a", "opus")
    check("forwards a model override", "--model" in command and "opus" in command)

    print(f"\n{len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
