"""Select source contents from the execution point recorded in the run context."""
import json
from pathlib import Path
import stat
import subprocess

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
