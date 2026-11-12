"""Limit the approximate token count of the root AGENTS.md."""
from pathlib import Path
import re
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

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
    from snapshot import execution_point, read_file, select_snapshot
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
