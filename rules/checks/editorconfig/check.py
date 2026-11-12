"""Require a root .editorconfig that states the shared baseline."""
from pathlib import Path
import sys


# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

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
    from snapshot import execution_point, read_file, select_snapshot
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
