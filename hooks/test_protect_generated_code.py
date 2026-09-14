#!/usr/bin/env python3
"""Tests for the generated-code protection hook.

Run: python hooks/test_protect_generated_code.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).parent / "protect_generated_code.py"


def run(payload, root, env=None):
    environment = {**os.environ, **(env or {})}
    environment.pop("GID_GENERATING", None)
    if env:
        environment.update(env)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=root,
        env=environment,
    )
    return result.returncode, result.stderr


def payload_for(path, root, tool="Edit"):
    return {"tool_name": tool, "cwd": str(root), "tool_input": {"file_path": str(path)}}


def main():
    failures = []

    def check(name, condition):
        if condition:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name}")
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src" / "auth").mkdir(parents=True)
        (root / "intent").mkdir()
        generated = root / "src" / "auth" / "reset.py"
        generated.write_text("# generated", encoding="utf-8")
        intent_doc = root / "intent" / "password-reset.md"
        intent_doc.write_text("# intent", encoding="utf-8")

        code, stderr = run(payload_for(generated, root), root)
        check("blocks an edit to generated code", code == 2)
        check("explains the remedy", "update that document" in stderr.lower())

        code, _ = run(payload_for(intent_doc, root), root)
        check("allows an edit to an intent document", code == 0)

        code, _ = run(payload_for(root / "README.md", root), root)
        check("allows an edit outside the generated root", code == 0)

        code, _ = run(payload_for(generated, root, tool="Write"), root)
        check("blocks Write as well as Edit", code == 2)

        code, _ = run(payload_for(generated, root, tool="Read"), root)
        check("allows reads of generated code", code == 0)

        code, _ = run(payload_for(generated, root), root, env={"GID_GENERATING": "1"})
        check("permits writes during a generation run", code == 0)

        nested = root / "src" / "auth" / "deep" / "inner.py"
        nested.parent.mkdir(parents=True)
        nested.write_text("# generated", encoding="utf-8")
        code, _ = run(payload_for(nested, root), root)
        check("blocks nested paths under the generated root", code == 2)

        config = root / ".governed-intent.json"
        config.write_text(
            json.dumps({"generated_paths": ["build/**"]}), encoding="utf-8"
        )
        code, _ = run(payload_for(generated, root), root)
        check("honors a configured generated root", code == 0)

        build_file = root / "build" / "out.js"
        build_file.parent.mkdir()
        build_file.write_text("// generated", encoding="utf-8")
        code, _ = run(payload_for(build_file, root), root)
        check("blocks the configured generated root", code == 2)

        config.write_text("{not json", encoding="utf-8")
        code, _ = run(payload_for(generated, root), root)
        check("falls back to defaults on unreadable config", code == 2)

        code, _ = run({"tool_name": "Edit", "cwd": str(root)}, root)
        check("ignores a payload with no file path", code == 0)

    print(f"\n{len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
