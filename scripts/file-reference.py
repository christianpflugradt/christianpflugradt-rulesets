#!/usr/bin/env python3
"""Compare a repository file byte-for-byte with rule-local reference files."""
import os
from pathlib import Path
import stat
import subprocess
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from snapshot import select_snapshot


def error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def main():
    rule_value = os.environ.get("PLEASE_RULE_DIRECTORY")
    target = os.environ.get("PLEASE_PARAM_TARGET")
    point = os.environ.get("PLEASE_EXECUTION_POINT", "check")
    if not rule_value or not target:
        return error("PLEASE_RULE_DIRECTORY and PLEASE_PARAM_TARGET are required")
    relative = Path(target)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return error("target must be a repository-relative path without traversal")
    try:
        selected = select_snapshot("check")
        root = Path.cwd().resolve()
        refs = Path(rule_value).resolve() / "licenses"
        if not refs.is_dir():
            return error("rule-local licenses directory is missing")
        candidates = sorted(p for p in refs.iterdir()
                            if not p.name.startswith(".") and stat.S_ISREG(p.lstat().st_mode))
        if not candidates:
            return error("no reference licenses found")
        if selected == "head":
            result = subprocess.run(["git", "ls-tree", "-z", "HEAD", "--", f":(literal){relative.as_posix()}"],
                                    cwd=root, capture_output=True, check=False)
            if result.returncode != 0:
                return error(result.stderr.decode(errors="replace").strip())
            if not result.stdout or result.stdout.split(b" ", 1)[0] not in (b"100644", b"100755"):
                print(f"FAIL: {target} is missing from HEAD or not a regular file")
                return 1
            result = subprocess.run(["git", "show", f"HEAD:{relative.as_posix()}"],
                                    cwd=root, capture_output=True, check=False)
            if result.returncode != 0:
                return error(result.stderr.decode(errors="replace").strip())
            content = result.stdout
        elif selected == "worktree":
            path = root / relative
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                print(f"FAIL: {target} is missing")
                return 1
            if not stat.S_ISREG(mode) or not path.resolve().is_relative_to(root):
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
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
