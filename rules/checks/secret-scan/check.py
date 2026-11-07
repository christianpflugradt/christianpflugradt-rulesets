"""Scan the working tree or HEAD contents with Gitleaks, without Git history."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


LEAK_EXIT = 10


def command(*args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        # Tool diagnostics can contain sensitive content; do not echo them.
        raise RuntimeError(f"{args[0]} failed (exit {result.returncode})")
    return result.stdout


def target_path(dest, raw):
    relative = Path(os.fsdecode(raw))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("unsafe snapshot path")
    target = dest / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def populate_worktree(dest):
    index = command("git", "ls-files", "--stage", "-z")
    if any(entry.startswith(b"160000 ") for entry in index.split(b"\0")):
        raise RuntimeError("Git submodules are outside snapshot coverage")
    raw = command("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for rel in sorted(set(raw.split(b"\0")) - {b""}):
        source = Path(os.fsdecode(rel))
        # A tracked directory may have been replaced by a symlink locally.
        if any(part.is_symlink() for part in (source, *source.parents)):
            continue
        try:
            mode = source.stat().st_mode
        except FileNotFoundError:
            continue  # Deleted working-tree files have no current contents.
        if not stat.S_ISREG(mode):
            raise RuntimeError(f"unsupported working-tree entry {ascii(str(source))}")
        shutil.copyfile(source, target_path(dest, rel))


def populate_commit(dest):
    # Read blobs directly: git archive honors export-ignore/export-subst.
    raw = command("git", "ls-tree", "-rz", "HEAD")
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, rel = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if mode == b"120000":
            continue  # Never follow symlinks.
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise RuntimeError(f"unsupported commit entry {ascii(os.fsdecode(rel))}")
        target_path(dest, rel).write_bytes(command("git", "cat-file", "blob", oid.decode("ascii")))


def findings_from(report, status):
    if status not in (0, LEAK_EXIT):
        raise RuntimeError(f"gitleaks failed (exit {status}); check the tool and scanner configuration")
    findings = json.loads(report.read_text())
    if not isinstance(findings, list) or any(
        not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key]
                                             for key in ("File", "RuleID"))
        for item in findings
    ):
        raise ValueError("invalid Gitleaks findings report")
    if bool(findings) != (status == LEAK_EXIT):
        raise ValueError("Gitleaks exit status and findings report disagree")
    return findings


def main():
    point = os.environ.get("HANNES_EXECUTION_POINT")
    if point not in ("check", "pre-push"):
        raise RuntimeError(f"unsupported execution point: {point!r}")
    scanner = shutil.which("gitleaks")
    if scanner is None:
        raise RuntimeError("gitleaks is not installed or is not on PATH")
    scanner = str(Path(scanner).resolve())
    with tempfile.TemporaryDirectory(prefix="hannes-secret-scan-") as temp:
        base = Path(temp)
        snapshot = base / "snapshot"
        snapshot.mkdir()
        report = base / "report.json"
        if point == "check":
            populate_worktree(snapshot)
        else:
            populate_commit(snapshot)
        # Use scanner configuration from the selected snapshot, including its
        # .gitleaksignore, rather than files from the caller's working tree.
        env = {key: value for key, value in os.environ.items()
               if key not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")}
        result = subprocess.run(
            [scanner, "dir", "--no-banner", "--redact", "--exit-code", str(LEAK_EXIT),
             "--report-format", "json", "--report-path", str(report), "."],
            cwd=snapshot, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        findings = findings_from(report, result.returncode)
        for finding in findings:
            print(f"FAIL: {ascii(finding['File'])}: {ascii(finding['RuleID'])}")
        if findings:
            print(f"Gitleaks detected {len(findings)} potential secret(s); values are not displayed.")
            return 1
        print(f"PASS: Gitleaks found no secrets ({point}, current snapshot only)")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
