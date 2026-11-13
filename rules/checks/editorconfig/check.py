"""Require a root .editorconfig that states the shared baseline."""
import json
import stat
import subprocess
from pathlib import Path
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

TARGET = ".editorconfig"
# Section glob -> required properties. Other sections and properties are the repository's own.
BASELINE = {
    None: {"root": "true"},
    "*": {"charset": "utf-8", "end_of_line": "lf", "insert_final_newline": "true",
          "trim_trailing_whitespace": "true", "indent_style": "space", "indent_size": "2"},
    "*.md": {"trim_trailing_whitespace": "false"},
    "Makefile": {"indent_style": "tab"},
}


def parse(text):
    """Return {section glob or None: {key: value}}; keys and values are case-insensitive."""
    sections = {None: {}}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line[0] == "[" and line[-1] == "]":
            current = line[1:-1]
            sections.setdefault(current, {})
        elif "=" in line:
            key, value = line.split("=", 1)
            sections[current][key.strip().lower()] = value.strip().lower()
    return sections


def violations(text):
    sections = parse(text)
    found = []
    for glob, required in BASELINE.items():
        label = "preamble" if glob is None else f"[{glob}]"
        if glob is not None and glob not in sections:
            found.append(f"{label} section is missing")
            continue
        for key, value in required.items():
            actual = sections[glob].get(key)
            if actual != value:
                found.append(f"{label} requires {key} = {value} (found {actual or 'nothing'})")
    return found


def main():
    if len(sys.argv) != 2:
        raise ValueError("expected one argument: context file")
    point = execution_point(sys.argv[1])
    content = read_file(select_snapshot(point), TARGET)
    if content is None:
        print(f"FAIL: {TARGET} is missing")
        return 1
    found = violations(content.decode("utf-8"))
    for message in found:
        print(f"FAIL: {TARGET} {message}")
    if not found:
        print(f"PASS: {TARGET} states the baseline ({point})")
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
