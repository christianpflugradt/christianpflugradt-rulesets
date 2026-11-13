"""Reject sensitive filenames without reading their contents."""
import json
import os
from pathlib import PurePosixPath
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


def prohibited(path):
    name = PurePosixPath(path).name
    environment = (name == ".env" or name.startswith(".env.")) and name not in (
        ".env.example", ".env.sample", ".env.template")
    return environment or name.endswith(".tfstate") or ".tfstate." in name


def command(*args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed (exit {result.returncode})")
    return result.stdout


def main():
    if len(sys.argv) != 2:
        raise ValueError("expected one argument: context file")
    point = execution_point(sys.argv[1])
    selected = select_snapshot(point)
    if selected == "worktree":
        raw = command("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        paths = {os.fsdecode(path) for path in raw.split(b"\0") if path and os.path.lexists(os.fsdecode(path))}
    else:
        raw = command("git", "ls-tree", "-rz", "--name-only", "HEAD")
        paths = {os.fsdecode(path) for path in raw.split(b"\0") if path}
    blocked = sorted(path for path in paths if prohibited(path))
    for path in blocked:
        print(f"FAIL: prohibited sensitive file {ascii(path)}")
    if not blocked:
        print(f"PASS: no prohibited sensitive filenames ({point})")
    return 1 if blocked else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
