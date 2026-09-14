#!/usr/bin/env python3
"""PreToolUse hook: block manual edits to generated code.

Reads a PreToolUse payload on stdin. Exits 2 to block the tool call when the
target path is inside a generated-code root, which tells the calling agent to
update the intent document and regenerate instead of patching the artifact.

Configuration lives in `.governed-intent.json` at the repository root:

    {
      "generated_paths": ["src/**"],
      "generation_env": "GID_GENERATING"
    }

`generated_paths` are gitignore-style globs evaluated against repo-relative
POSIX paths. When the environment variable named by `generation_env` is set to
a non-empty value, writes are permitted — that is the Stage 6 escape hatch for
the code generation agent itself.
"""
import fnmatch
import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "generated_paths": ["src/**"],
    "generation_env": "GID_GENERATING",
}

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

BLOCK_MESSAGE = """Blocked: {path} is generated code and is read-only under Governed Intent Development.

Generated code is a build artifact. Editing it severs the chain between the intent
document and the implementation, and makes the compliance check meaningless.

Do this instead:
  1. Identify the intent document this unit was generated from.
  2. Update that document to describe the behavior you wanted.
  3. Re-enter the workflow via the Intent Maintenance Agent and regenerate.

If you are the code generation agent running Stage 6, set {env}=1 for that run."""


def load_config(root):
    path = root / ".governed-intent.json"
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"governed-intent: cannot read {path}: {exc}", file=sys.stderr)
        return DEFAULT_CONFIG
    return {**DEFAULT_CONFIG, **config}


def repo_root(payload):
    for key in ("cwd", "project_dir"):
        value = payload.get(key)
        if value:
            return Path(value)
    return Path.cwd()


def relative_path(target, root):
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def is_protected(rel_path, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # "src/**" should also match "src/main.py", which fnmatch does not do.
        prefix = pattern.rstrip("*").rstrip("/")
        if prefix and (rel_path == prefix or rel_path.startswith(prefix + "/")):
            return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") not in WRITE_TOOLS:
        return 0

    target = payload.get("tool_input", {}).get("file_path")
    if not target:
        return 0

    root = repo_root(payload)
    config = load_config(root)

    if os.environ.get(config["generation_env"]):
        return 0

    rel_path = relative_path(Path(target), root)
    if rel_path is None or not is_protected(rel_path, config["generated_paths"]):
        return 0

    print(
        BLOCK_MESSAGE.format(path=rel_path, env=config["generation_env"]),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
