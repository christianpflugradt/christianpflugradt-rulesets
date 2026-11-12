"""Validate the Conventional Commits 1.0.0 header of the commit message.

Exit codes: 0 = PASS, 1 = FAIL, 2 = ERROR.
Invoked at commit-msg with the run context file and the scopes file as arguments.
Only the header is validated; body and footer are not inspected.
"""
import json
from pathlib import Path
import sys


class Fail(Exception):
    """A verdict about the commit message, never a technical failure."""


def read_lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


def validate(header, types, scopes):
    if ": " not in header:
        raise Fail("Expected '<type>[optional scope][!]: <description>'")
    prefix, description = header.split(": ", 1)
    if not description.strip():
        raise Fail("Commit description must not be blank")
    if prefix.endswith("!"):
        prefix = prefix[:-1]
    kind, scope = prefix, ""
    if prefix.endswith(")") and "(" in prefix:
        kind, _, scope = prefix[:-1].partition("(")
        if not scope:
            raise Fail("Commit scope must not be empty")
    elif "(" in prefix or ")" in prefix:
        raise Fail("Invalid commit scope syntax")
    if not kind:
        raise Fail("Commit type must not be empty")
    if kind not in types:
        raise Fail(f"Commit type '{kind}' is not allowed")
    if scope:
        if "(" in scope or ")" in scope:
            raise Fail("Invalid commit scope syntax")
        if scope not in scopes:
            raise Fail(f"Commit scope '{scope}' is not allowed")


def main():
    if len(sys.argv) != 3:
        raise ValueError("expected arguments: context file and scopes file")
    context = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if context.get("execution_point") != "commit-msg":
        raise ValueError("Expected the commit-msg execution point")
    message = read_lines(context["commit_message"]["file"])
    types = read_lines(Path(__file__).with_name("commit-types.txt"))
    scopes = read_lines(sys.argv[2])
    try:
        if not message:
            raise Fail("Commit message is empty")
        validate(message[0], types, scopes)
    except Fail as verdict:
        print(f"FAIL commit-message: {verdict}")
        return 1
    print("PASS commit-message")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError) as exc:
        print(f"ERROR commit-message: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
