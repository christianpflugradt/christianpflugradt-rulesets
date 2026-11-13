"""Limit the approximate token count of the root AGENTS.md."""
import json
import stat
import subprocess
from pathlib import Path
import re
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

TARGET = "AGENTS.md"


def require_arguments(count):
    if len(sys.argv) != count + 1:
        raise ValueError(f"expected {count} arguments: context file and max_tokens")


def count_tokens(text):
    """Approximate tokens as runs of word characters and single other marks."""
    return len(re.findall(r"\w+|[^\w\s]", text))


def parse_limit(value):
    if value is None or not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
        raise ValueError("max_tokens must be a positive integer")
    return int(value)


def main():
    require_arguments(2)
    point = execution_point(sys.argv[1])
    limit = parse_limit(sys.argv[2])
    content = read_file(select_snapshot(point), TARGET)
    if content is None:
        print(f"PASS: {TARGET} is absent; nothing to limit ({point})")
        return 0
    count = count_tokens(content.decode("utf-8"))
    if count > limit:
        print(f"FAIL: {TARGET} has {count} approximate tokens (limit {limit})")
        return 1
    print(f"PASS: {TARGET} has {count} approximate tokens (limit {limit})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
