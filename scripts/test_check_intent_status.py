#!/usr/bin/env python3
"""Tests for the intent status gate.

Run: python scripts/test_check_intent_status.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_intent_status import check, intent_path_for, status_of


def write_intent(root, unit_path, status):
    path = root / "intent" / f"{unit_path}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nunit: {unit_path}\nversion: 0.1.0\nstatus: {status}\nauthor: t\n---\n\n# Intent\n",
        encoding="utf-8",
    )
    return path


def main():
    failures = []

    def expect(name, condition):
        if condition:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name}")
            failures.append(name)

    expect(
        "maps a unit path to an intent document",
        intent_path_for("src/auth/password-reset", "src", "intent")
        == Path("intent/auth/password-reset.md"),
    )
    expect(
        "tolerates a trailing slash",
        intent_path_for("src/auth/reset/", "src", "intent") == Path("intent/auth/reset.md"),
    )
    expect(
        "rejects a path outside the implementation root",
        intent_path_for("docs/readme", "src", "intent") is None,
    )
    expect(
        "honors a custom implementation root",
        intent_path_for("lib/auth/reset", "lib", "specs") == Path("specs/auth/reset.md"),
    )

    import os

    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        os.chdir(root)

        approved = write_intent(root, "auth/password-reset", "approved")
        draft = write_intent(root, "auth/session", "draft")
        expect("reads an approved status", status_of(approved) == "approved")
        expect("reads a draft status", status_of(draft) == "draft")

        expect(
            "passes an approved unit",
            check(["src/auth/password-reset"], "src", "intent") == [],
        )

        result = check(["src/auth/session"], "src", "intent")
        expect("blocks a draft unit", len(result) == 1 and "draft" in result[0])

        result = check(["src/payments/refund"], "src", "intent")
        expect("blocks a unit with no intent document", len(result) == 1 and "no intent" in result[0])

        result = check(["docs/guide"], "src", "intent")
        expect("blocks a path outside the implementation root", len(result) == 1)

        no_frontmatter = root / "intent" / "auth" / "broken.md"
        no_frontmatter.write_text("# no frontmatter\n", encoding="utf-8")
        result = check(["src/auth/broken"], "src", "intent")
        expect("blocks a document with no frontmatter", len(result) == 1 and "None" in result[0])

        result = check(["src/auth/password-reset", "src/auth/session"], "src", "intent")
        expect("reports only the failing unit in a mixed set", len(result) == 1)

        os.chdir(original_cwd)

    print(f"\n{len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
