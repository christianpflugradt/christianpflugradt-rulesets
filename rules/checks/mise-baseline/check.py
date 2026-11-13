"""Require the Please Behave version pin and the format and verify tasks in the root mise.toml."""
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


def read_file(selected, name):
    """Return the bytes of a root file in the selected snapshot, or None when it is absent."""
    if selected == "head":
        listed = subprocess.run(["git", "ls-tree", "-z", "HEAD", "--", f":(literal){name}"],
                                capture_output=True, check=False)
        if listed.returncode != 0:
            raise RuntimeError(listed.stderr.decode(errors="replace").strip())
        if not listed.stdout:
            return None
        if listed.stdout.split(b" ", 1)[0] not in (b"100644", b"100755"):
            raise RuntimeError(f"{name} is not a regular file in HEAD")
        shown = subprocess.run(["git", "show", f"HEAD:{name}"], capture_output=True, check=False)
        if shown.returncode != 0:
            raise RuntimeError(shown.stderr.decode(errors="replace").strip())
        return shown.stdout
    path = Path.cwd().resolve() / name
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"{name} is not a regular file")
    return path.read_bytes()

TARGET = "mise.toml"
TOOLS = ["github:please-behave/cli"]
TASKS = ["format", "verify"]


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


def violations(document, tools=TOOLS, tasks=TASKS):
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
    if len(sys.argv) != 2:
        raise ValueError("expected argument: context file")
    try:
        import tomllib
    except ImportError:
        raise RuntimeError("Python 3.11+ is required to parse mise.toml") from None
    point = execution_point(sys.argv[1])
    content = read_file(select_snapshot(point), TARGET)
    if content is None:
        print(f"FAIL: {TARGET} is missing")
        return 1
    try:
        document = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"{TARGET} is not valid UTF-8 TOML: {exc}") from None
    found = violations(document)
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
