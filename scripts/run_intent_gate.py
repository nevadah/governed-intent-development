#!/usr/bin/env python3
"""Run a Governed Intent Development agent as a CI gate.

Invokes the compliance or security agent headlessly against an intent document
and its implementation, prints the agent's report, and exits non-zero when the
gate fails.

    python scripts/run_intent_gate.py compliance \
        --intent intent/auth/password-reset.md \
        --implementation src/auth/password-reset

    python scripts/run_intent_gate.py security \
        --intent intent/auth/password-reset.md \
        --implementation src/auth/password-reset

The agent is given read-only tools. It cannot modify the implementation it is
judging, which is the property that makes it an independent check.

Requires the `claude` CLI on PATH and ANTHROPIC_API_KEY in the environment.
Use --dry-run to print the command without invoking it.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

AGENTS = {
    "compliance": {
        "prompt": "agents/compliance-agent.md",
        "failing_results": {"FAIL"},
        "task": (
            "Verify the implementation against the intent document and produce a "
            "compliance report in exactly the format your instructions specify."
        ),
    },
    "security": {
        "prompt": "agents/security-agent.md",
        "failing_results": {"FINDINGS"},
        "task": (
            "Perform an adversarial security audit of the implementation and produce a "
            "security audit report in exactly the format your instructions specify."
        ),
    },
}

READ_ONLY_TOOLS = "Read,Grep,Glob"
RESULT_PATTERN = re.compile(r"^\*\*Result:\*\*\s*(?!.*\|)([A-Z_]+)", re.MULTILINE)


def strip_frontmatter(text):
    """Return the system prompt body, dropping subagent YAML frontmatter."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def parse_result(report):
    """Extract the report's Result value, ignoring the format template line."""
    match = RESULT_PATTERN.search(report)
    return match.group(1) if match else None


def build_command(agent, intent, implementation, model):
    system_prompt = strip_frontmatter(Path(agent["prompt"]).read_text(encoding="utf-8"))
    task = (
        f"{agent['task']}\n\n"
        f"Intent document: {intent}\n"
        f"Implementation: {implementation}\n\n"
        "Read both before reporting. Report only what you can support from what you read."
    )
    command = [
        "claude",
        "-p",
        task,
        "--append-system-prompt",
        system_prompt,
        "--allowedTools",
        READ_ONLY_TOOLS,
    ]
    if model:
        command += ["--model", model]
    return command


def write_step_summary(title, report):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write(f"## {title}\n\n{report}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=sorted(AGENTS))
    parser.add_argument("--intent", required=True, help="Path to the intent document")
    parser.add_argument(
        "--implementation", required=True, help="Path to the generated implementation"
    )
    parser.add_argument("--model", help="Override the model used for this gate")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the command without running it"
    )
    args = parser.parse_args()

    agent = AGENTS[args.gate]
    command = build_command(agent, args.intent, args.implementation, args.model)

    if args.dry_run:
        print(" ".join(repr(part) if " " in part else part for part in command[:6]), "...")
        return 0

    result = subprocess.run(command, capture_output=True, text=True)
    report = result.stdout.strip()

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print(f"{args.gate} gate: agent invocation failed", file=sys.stderr)
        return 1

    print(report)
    write_step_summary(f"{args.gate.title()} gate", report)

    verdict = parse_result(report)
    if verdict is None:
        print(
            f"{args.gate} gate: could not find a Result line in the report",
            file=sys.stderr,
        )
        return 1

    if verdict in agent["failing_results"]:
        print(f"{args.gate} gate: {verdict} — blocking merge", file=sys.stderr)
        return 1

    print(f"{args.gate} gate: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
