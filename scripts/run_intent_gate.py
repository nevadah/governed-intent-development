#!/usr/bin/env python3
"""Run a Governed Intent Development agent as a CI gate.

Invokes the compliance or security agent against an intent document and its
implementation, prints the agent's report, and exits non-zero when the gate
fails.

    python scripts/run_intent_gate.py compliance \
        --intent intent/auth/password-reset.md \
        --implementation src/auth/password-reset

The agent's system prompt is read from the agent definition in `agents/`, so
the CI gate and the interactive subagent are the same agent by construction.

Any agent CLI can drive the gate. Pick one with --runner:

    --runner claude                    (default)
    --runner codex
    --runner gemini
    --runner custom --command "..."    anything else

The agent must be unable to modify the implementation it is judging — an
observer that can edit what it judges is not an independent check. Runners
that cannot be shown to enforce that are refused unless you pass
--allow-unenforced-read-only, which downgrades the gate and labels the output
accordingly. Run --list-runners to see where each one stands.
"""
import argparse
import os
import re
import shlex
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

# read_only levels:
#   "enforced"   — the tool's own documentation states the agent cannot write.
#   "unverified" — no documented mechanism was confirmed either way.
#   "advisory"   — the restriction exists only as an instruction in the prompt.
#
# Only "enforced" runs without --allow-unenforced-read-only. See runners.md for
# the provenance of each claim and the date it was checked.
RUNNERS = {
    "claude": {
        "read_only": "enforced",
        "key_env": "ANTHROPIC_API_KEY",
        "argv": [
            "claude",
            "-p",
            "{task}",
            "--append-system-prompt",
            "{system_prompt}",
            "--allowedTools",
            "Read,Grep,Glob",
        ],
        "stdin": None,
        "model_flag": "--model",
    },
    "codex": {
        "read_only": "enforced",
        "key_env": "CODEX_API_KEY",
        # Codex has no documented flag for appending a system prompt, so the
        # prompt and the task are concatenated and piped in. `exec -` reads the
        # prompt from stdin; the final agent message goes to stdout.
        "argv": ["codex", "exec", "-", "--sandbox", "read-only", "--skip-git-repo-check"],
        "stdin": "{system_prompt}\n\n---\n\n{task}",
        "model_flag": None,
    },
    "gemini": {
        "read_only": "unverified",
        "key_env": None,
        # -p forces non-interactive mode and is appended to stdin, so stdin
        # carries the system prompt and -p carries the task.
        "argv": ["gemini", "-p", "{task}", "--output-format", "text"],
        "stdin": "{system_prompt}",
        "model_flag": "--model",
    },
}

UNENFORCED_NOTICE = (
    "\n\nYou have read-only access for this audit. Do not create, modify, or delete "
    "any file. Report findings only."
)

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


def substitute(template, values):
    """Replace whole-token placeholders in an argv list.

    Tokens are matched exactly and never formatted, so braces inside a prompt
    or a report cannot be mistaken for placeholders.
    """
    return [values.get(part, part) for part in template]


def resolve_runner(name, command):
    if name == "custom":
        if not command:
            raise SystemExit("--runner custom requires --command")
        return {
            "read_only": "advisory",
            "key_env": None,
            "argv": shlex.split(command),
            "stdin": None,
            "model_flag": None,
        }
    if name not in RUNNERS:
        known = ", ".join(sorted(RUNNERS))
        raise SystemExit(f"unknown runner {name!r}; choose from {known} or custom")
    return RUNNERS[name]


def build_invocation(agent, runner, intent, implementation, model):
    """Return (argv, stdin_text) for this gate."""
    system_prompt = strip_frontmatter(Path(agent["prompt"]).read_text(encoding="utf-8"))
    if runner["read_only"] != "enforced":
        system_prompt += UNENFORCED_NOTICE

    task = (
        f"{agent['task']}\n\n"
        f"Intent document: {intent}\n"
        f"Implementation: {implementation}\n\n"
        "Read both before reporting. Report only what you can support from what you read."
    )

    values = {"{task}": task, "{system_prompt}": system_prompt}
    argv = substitute(runner["argv"], values)

    if model and runner.get("model_flag"):
        argv += [runner["model_flag"], model]

    stdin_text = None
    if runner.get("stdin"):
        stdin_text = runner["stdin"].replace("{system_prompt}", system_prompt).replace("{task}", task)

    return argv, stdin_text


def write_step_summary(title, report):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write(f"## {title}\n\n{report}\n")


def list_runners():
    print("Runners:\n")
    rows = sorted(RUNNERS.items()) + [("custom", {"read_only": "advisory", "key_env": None})]
    for name, runner in rows:
        key = runner["key_env"] or "-"
        print(f"  {name:<8} read-only: {runner['read_only']:<11} key env: {key}")
    print(
        "\n  enforced    the tool's documentation states the agent cannot write files\n"
        "  unverified  no documented mechanism confirmed either way\n"
        "  advisory    the agent is only asked not to write\n"
        "\nAnything but 'enforced' requires --allow-unenforced-read-only. See\n"
        "workflow/runners.md for where each claim comes from."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=sorted(AGENTS), nargs="?")
    parser.add_argument("--intent", help="Path to the intent document")
    parser.add_argument("--implementation", help="Path to the generated implementation")
    parser.add_argument("--runner", default="claude", help="Agent CLI to drive the gate")
    parser.add_argument("--command", help="Command template for --runner custom")
    parser.add_argument("--model", help="Override the model used for this gate")
    parser.add_argument(
        "--allow-unenforced-read-only",
        action="store_true",
        help="Permit a runner that cannot be shown to prevent the agent from writing",
    )
    parser.add_argument("--list-runners", action="store_true", help="List available runners")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running it")
    args = parser.parse_args()

    if args.list_runners:
        return list_runners()

    missing = [
        name
        for name, value in [
            ("gate", args.gate),
            ("--intent", args.intent),
            ("--implementation", args.implementation),
        ]
        if not value
    ]
    if missing:
        parser.error(f"missing required argument(s): {', '.join(missing)}")

    agent = AGENTS[args.gate]
    runner = resolve_runner(args.runner, args.command)
    enforced = runner["read_only"] == "enforced"

    if not enforced and not args.allow_unenforced_read_only:
        print(
            f"{args.runner}: read-only file access is {runner['read_only']}, not enforced.\n"
            "The compliance and security gates exist to be independent of the code they judge,\n"
            "and an agent that can edit that code is not independent.\n"
            "Re-run with --allow-unenforced-read-only to accept a weaker gate.",
            file=sys.stderr,
        )
        return 2

    argv, stdin_text = build_invocation(agent, runner, args.intent, args.implementation, args.model)

    if args.dry_run:
        print(shlex.join(argv[:3]), "...")
        return 0

    result = subprocess.run(argv, input=stdin_text, capture_output=True, text=True)
    report = result.stdout.strip()

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print(f"{args.gate} gate: agent invocation failed", file=sys.stderr)
        return 1

    print(report)
    title = f"{args.gate.title()} gate"
    if not enforced:
        title += f" ({runner['read_only']} read-only)"
    write_step_summary(title, report)

    verdict = parse_result(report)
    if verdict is None:
        print(f"{args.gate} gate: could not find a Result line in the report", file=sys.stderr)
        return 1

    if verdict in agent["failing_results"]:
        print(f"{args.gate} gate: {verdict} — blocking merge", file=sys.stderr)
        return 1

    print(f"{args.gate} gate: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
