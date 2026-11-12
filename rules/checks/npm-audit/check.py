"""Audit each tracked package-lock.json for high and critical advisories; no lockfile means PASS."""
import json
import os
import subprocess
import sys

LEVELS = ("high", "critical")


def audit(directory):
    result = subprocess.run(["npm", "audit", "--audit-level=high", "--json"], cwd=directory,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        report = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"npm audit returned no JSON for {directory}") from None
    if not isinstance(report, dict) or "error" in report:
        raise RuntimeError(f"npm audit could not audit {directory}")
    counts = report.get("metadata", {}).get("vulnerabilities", {})
    return sum(counts.get(level, 0) for level in LEVELS)


def main():
    listed = subprocess.run(["git", "ls-files", "-z"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if listed.returncode:
        raise RuntimeError("git ls-files failed")
    locks = sorted(path for path in map(os.fsdecode, listed.stdout.split(b"\0"))
                   if os.path.basename(path) == "package-lock.json" and os.path.isfile(path))
    if not locks:
        print("PASS: no package-lock.json to audit")
        return 0
    failed = False
    for lock in locks:
        directory = os.path.dirname(lock) or "."
        found = audit(directory)
        if found:
            print(f"FAIL: {found} high or critical advisories in {lock}")
            failed = True
    if not failed:
        print(f"PASS: no high or critical advisories in {len(locks)} lockfiles")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
