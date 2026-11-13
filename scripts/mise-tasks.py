#!/usr/bin/env python3
"""Require tools and tasks in the root mise.toml: mise-tasks.py CONTEXT [--tools A,B] [--tasks X,Y]."""
from pathlib import Path
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

TARGET = "mise.toml"


def parse_arguments(argv):
    """Return (context file, tools, tasks) from the command line."""
    if len(argv) < 2 or len(argv) % 2:
        raise ValueError("expected arguments: context file, optional --tools and --tasks lists")
    lists = {"--tools": [], "--tasks": []}
    for flag, value in zip(argv[2::2], argv[3::2]):
        if flag not in lists:
            raise ValueError(f"unknown argument: {flag}")
        lists[flag] = [item for item in value.split(",") if item]
    return argv[1], lists["--tools"], lists["--tasks"]


def runnable(task):
    """A task counts when it states a command or dependencies; an echo placeholder qualifies."""
    if isinstance(task, str):
        return bool(task.strip())
    if isinstance(task, dict):
        for key in ("run", "depends"):
            value = task.get(key)
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, list) and value:
                return True
    return False


def violations(document, tools, tasks):
    found = []
    declared = document.get("tools")
    declared = declared if isinstance(declared, dict) else {}
    for name in tools:
        if name not in declared:
            found.append(f"[tools] does not pin {name}")
    defined = document.get("tasks")
    defined = defined if isinstance(defined, dict) else {}
    for name in tasks:
        if not runnable(defined.get(name)):
            found.append(f"task {name} is missing or has neither run nor depends")
    return found


def main():
    from snapshot import execution_point, read_file, select_snapshot
    context_file, tools, tasks = parse_arguments(sys.argv)
    try:
        import tomllib
    except ImportError:
        raise RuntimeError("Python 3.11+ is required to parse mise.toml") from None
    point = execution_point(context_file)
    content = read_file(select_snapshot(point), TARGET)
    if content is None:
        print(f"FAIL: {TARGET} is missing")
        return 1
    try:
        document = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"{TARGET} is not valid UTF-8 TOML: {exc}") from None
    found = violations(document, tools, tasks)
    for message in found:
        print(f"FAIL: {TARGET} {message}")
    if not found:
        print(f"PASS: {TARGET} defines the required tools and tasks ({point})")
    return 1 if found else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
