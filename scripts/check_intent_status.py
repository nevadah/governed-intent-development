#!/usr/bin/env python3
"""Assert that every changed implementation unit has an approved intent document.

This is the gate that needs no model and no API key. It enforces at the merge
boundary what the workflow enforces by process: code generation cannot begin
until the intent document is approved.

    python scripts/check_intent_status.py --units changed_units.txt
    python scripts/check_intent_status.py src/auth/password-reset

Unit paths are mapped to intent documents by the recommended convention:

    src/auth/password-reset  ->  intent/auth/password-reset.md

Override the roots with --implementation-root and --intent-root when a project
maps differently.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

APPROVED = "approved"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def intent_path_for(unit, implementation_root, intent_root):
    unit = unit.strip().rstrip("/")
    prefix = implementation_root.rstrip("/") + "/"
    if not unit.startswith(prefix):
        return None
    return Path(intent_root) / (unit[len(prefix) :] + ".md")


def status_of(path):
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        return None
    frontmatter = yaml.safe_load(match.group(1))
    if not isinstance(frontmatter, dict):
        return None
    return frontmatter.get("status")


def check(units, implementation_root, intent_root):
    failures = []
    for unit in units:
        intent = intent_path_for(unit, implementation_root, intent_root)
        if intent is None:
            failures.append(f"{unit}: outside the implementation root {implementation_root}/")
            continue
        if not intent.exists():
            failures.append(f"{unit}: no intent document at {intent}")
            continue
        status = status_of(intent)
        if status != APPROVED:
            failures.append(f"{unit}: {intent} has status {status!r}, expected 'approved'")
            continue
        print(f"  ok  {unit} <- {intent}")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("units", nargs="*", help="Implementation unit paths")
    parser.add_argument("--units", dest="units_file", help="File of unit paths, one per line")
    parser.add_argument("--implementation-root", default="src")
    parser.add_argument("--intent-root", default="intent")
    args = parser.parse_args()

    units = list(args.units)
    if args.units_file:
        units += [
            line.strip()
            for line in Path(args.units_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    if not units:
        print("No implementation units changed.")
        return 0

    failures = check(units, args.implementation_root, args.intent_root)
    for failure in failures:
        print(f"  FAIL  {failure}", file=sys.stderr)

    print(f"\n{len(units)} unit(s) checked, {len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
