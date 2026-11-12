"""Limit the approximate token count of the root AGENTS.md."""
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from snapshot import select_snapshot

TARGET = "AGENTS.md"


def count_tokens(text):
    """Approximate tokens as runs of word characters and single other marks."""
    return len(re.findall(r"\w+|[^\w\s]", text))


def parse_limit(value):
    if value is None or not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
        raise ValueError("max_tokens must be a positive integer")
    return int(value)


def read_target(selected):
    """Return the file bytes of the selected snapshot, or None when absent."""
    if selected == "head":
        listed = subprocess.run(["git", "ls-tree", "-z", "HEAD", "--", f":(literal){TARGET}"],
                                capture_output=True, check=False)
        if listed.returncode != 0:
            raise RuntimeError(listed.stderr.decode(errors="replace").strip())
        if not listed.stdout:
            return None
        if listed.stdout.split(b" ", 1)[0] not in (b"100644", b"100755"):
            raise RuntimeError(f"{TARGET} is not a regular file in HEAD")
        shown = subprocess.run(["git", "show", f"HEAD:{TARGET}"], capture_output=True, check=False)
        if shown.returncode != 0:
            raise RuntimeError(shown.stderr.decode(errors="replace").strip())
        return shown.stdout
    path = Path.cwd().resolve() / TARGET
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"{TARGET} is not a regular file")
    return path.read_bytes()


def main():
    limit = parse_limit(os.environ.get("PLEASE_PARAM_MAX_TOKENS"))
    point = os.environ.get("PLEASE_EXECUTION_POINT")
    content = read_target(select_snapshot())
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
