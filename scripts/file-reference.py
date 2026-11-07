#!/usr/bin/env python3
"""Compare a repository file byte-for-byte with rule-local reference files."""
import os
from pathlib import Path
import subprocess
import sys


def error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def main():
    root = Path.cwd().resolve()
    rule_value = os.environ.get("HANNES_RULE_DIRECTORY")
    target = os.environ.get("HANNES_PARAM_TARGET")
    point = os.environ.get("HANNES_EXECUTION_POINT", "check")
    if not rule_value or not target:
        return error("HANNES_RULE_DIRECTORY and HANNES_PARAM_TARGET are required")
    relative = Path(target)
    if relative.is_absolute() or not relative.parts or any(p in ("..", ".") for p in relative.parts):
        return error("target must be a repository-relative path without traversal")
    rule_dir = Path(rule_value).resolve()
    refs = rule_dir / "licenses"
    if not refs.is_dir():
        return error("rule-local licenses directory is missing")
    candidates = sorted(p for p in refs.iterdir() if p.is_file() and not p.is_symlink() and not p.name.startswith("."))
    if not candidates:
        return error("no reference licenses found")
    try:
        if point == "pre-push":
            result = subprocess.run(["git", "show", f"HEAD:{relative.as_posix()}"], cwd=root, capture_output=True, check=False)
            if result.returncode != 0:
                print(f"FAIL: {target} is missing from HEAD")
                return 1
            content = result.stdout
        elif point == "check":
            path = root / relative
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                print(f"FAIL: {target} is missing or not a regular repository file")
                return 1
            content = path.read_bytes()
        else:
            return error(f"unsupported execution point: {point}")
        for reference in candidates:
            if content == reference.read_bytes():
                print(f"PASS: {target} matches {reference.name}")
                return 0
        print(f"FAIL: {target} does not exactly match any of {len(candidates)} allowed licenses")
        return 1
    except (OSError, subprocess.SubprocessError) as exc:
        return error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
