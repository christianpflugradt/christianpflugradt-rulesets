"""Select source contents without changing existing execution-point semantics."""
import os


def select_snapshot(default_point=None):
    point = os.environ.get("PLEASE_EXECUTION_POINT", default_point)
    explicit = os.environ.get("PLEASE_PARAM_SNAPSHOT")
    implicit = {"pre-commit": "worktree", "check": "worktree", "pre-push": "head"}.get(point)
    if explicit is not None and explicit not in ("head", "worktree"):
        raise ValueError("snapshot must be head or worktree")
    if implicit:
        if explicit is not None and explicit != implicit:
            raise ValueError("snapshot conflicts with the execution point")
        return implicit
    if not point or explicit is None:
        raise ValueError("custom execution points require an explicit snapshot")
    return explicit
