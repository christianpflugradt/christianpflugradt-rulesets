"""Require the license file to match one of the approved reference licenses in the rule's licenses directory."""
import json
from pathlib import Path
import stat
import subprocess
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True

SNAPSHOTS = {"pre-commit": "worktree", "check": "worktree", "pre-push": "head"}


def execution_point(context_file):
    with open(context_file, encoding="utf-8") as handle:
        point = json.load(handle).get("execution_point")
    if not isinstance(point, str) or not point:
        raise ValueError("run context has no execution point")
    return point


def select_snapshot(point):
    if point not in SNAPSHOTS:
        raise ValueError(f"unsupported execution point: {point}")
    return SNAPSHOTS[point]


def error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def main():
    if len(sys.argv) != 4:
        return error("expected arguments: context file, target and licenses directory")
    context_file, target, licenses = sys.argv[1:]
    relative = Path(target)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        return error("target must be a repository-relative path without traversal")
    try:
        selected = select_snapshot(execution_point(context_file))
        root = Path.cwd().resolve()
        refs = Path(licenses).resolve()
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
        else:
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
        for reference in candidates:
            if content == reference.read_bytes():
                print(f"PASS: {target} matches {reference.name}")
                return 0
        print(f"FAIL: {target} does not exactly match any of {len(candidates)} allowed licenses")
        return 1
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return error(str(exc))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
