"""Reject sensitive filenames without reading their contents."""
import os
from pathlib import PurePosixPath
import subprocess
import sys


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
    point = os.environ.get("PLEASE_EXECUTION_POINT")
    if point == "check":
        raw = command("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        paths = {os.fsdecode(path) for path in raw.split(b"\0") if path and os.path.lexists(os.fsdecode(path))}
    elif point == "pre-push":
        raw = command("git", "ls-tree", "-rz", "--name-only", "HEAD")
        paths = {os.fsdecode(path) for path in raw.split(b"\0") if path}
    else:
        raise RuntimeError(f"unsupported execution point: {point!r}")
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
