"""Require the shared structure of release.yml; scripts, artifacts and candidate steps stay with consumers."""
import json
import re
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

PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def parse(content):
    """Return the workflow as a dict; invalid YAML or a non-mapping document is a technical failure."""
    result = subprocess.run(["yq", "--output-format=json", "."], input=content, capture_output=True)
    if result.returncode:
        raise ValueError(f"yq cannot parse the workflow: {result.stderr.decode(errors='replace').strip()}")
    document = json.loads(result.stdout)
    if not isinstance(document, dict):
        raise ValueError("the workflow is not a YAML mapping")
    return document


def flag(value):
    """Compare booleans and their quoted spellings alike."""
    return str(value).lower()


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def as_dict(value):
    return value if isinstance(value, dict) else {}


def triggers(document):
    """Map each trigger event to its configuration, whichever form `on` is written in."""
    declared = document.get("on")
    if isinstance(declared, dict):
        return declared
    return {event: None for event in as_list(declared) if isinstance(event, str)}


def jobs(document):
    return {name: as_dict(job) for name, job in as_dict(document.get("jobs")).items()}


def steps(job):
    return [as_dict(step) for step in as_list(job.get("steps"))]


def uses(step, action):
    """True when the step uses the action, whatever its version reference."""
    return str(step.get("uses", "")).split("@", 1)[0] == action


def with_value(step, key):
    return as_dict(step.get("with")).get(key)


def runs(step, command):
    return str(step.get("run", "")).strip() == command


def please_behave(step, point):
    return uses(step, "please-behave/action") and with_value(step, "execution-point") == point


def grants_write(job):
    permissions = job.get("permissions")
    if isinstance(permissions, str):
        return permissions == "write-all"
    return "write" in as_dict(permissions).values()


def common(document):
    """Rules every shared workflow follows: read-only default permissions, timeouts and pinned actions."""
    found = []
    if document.get("permissions") != {"contents": "read"}:
        found.append("top-level permissions must be exactly contents: read")
    for job_id, job in jobs(document).items():
        reusable = "uses" in job
        if "timeout-minutes" not in job and not reusable:
            found.append(f"job {job_id} sets no timeout-minutes")
        references = [job["uses"]] if reusable else []
        references += [step["uses"] for step in steps(job) if "uses" in step]
        for reference in references:
            reference = str(reference)
            if not reference.startswith("./") and not PINNED.match(reference):
                found.append(f"job {job_id} uses {reference}, which is not pinned to a full commit SHA")
    return found


def run(argv, name, violations):
    """Evaluate one workflow file of the snapshot selected by the execution point; return the exit status."""
    if len(argv) != 2:
        raise ValueError("expected argument: context file")
    point = execution_point(argv[1])
    target = f".github/workflows/{name}"
    content = read_file(select_snapshot(point), target)
    if content is None:
        print(f"FAIL: {target} is missing")
        return 1
    found = violations(parse(content))
    for message in found:
        print(f"FAIL: {target} {message}")
    if not found:
        print(f"PASS: {target} follows the shared structure ({point})")
    return 1 if found else 0

REQUIRED_JOBS = ("plan", "release-readiness", "release-candidate", "publish")
REQUIRED_OUTPUTS = ("release", "version", "source_sha")
RELEASE_GATE = "needs.plan.outputs.release == 'true'"
SOURCE_REF = "${{ needs.plan.outputs.source_sha }}"


def condition(job):
    return " ".join(str(job.get("if", "")).split())


def violations(document):
    found = []
    if document.get("name") != "Release":
        found.append('name must be "Release"')
    events = set(triggers(document))
    if "workflow_dispatch" not in events or events - {"workflow_dispatch", "schedule"}:
        found.append("must be triggered by workflow_dispatch, optionally also by schedule")
    concurrency = as_dict(document.get("concurrency"))
    if concurrency.get("group") != "release-main" or flag(concurrency.get("cancel-in-progress")) != "false":
        found.append("concurrency must use group release-main with cancel-in-progress: false")
    if flag(as_dict(document.get("env")).get("MISE_AUTO_INSTALL")) != "false":
        found.append("env must set MISE_AUTO_INSTALL to 'false' so jobs keep their explicit tool subsets")

    listed = jobs(document)
    found += [f"job {name} is missing" for name in REQUIRED_JOBS if name not in listed]
    plan, publish = listed.get("plan", {}), listed.get("publish", {})
    others = [name for name in listed if name not in ("plan", "publish")]

    if "github.ref == 'refs/heads/main'" not in condition(plan):
        found.append("job plan must run only on refs/heads/main")
    outputs = as_dict(plan.get("outputs"))
    found += [f"job plan lacks the output {name}" for name in REQUIRED_OUTPUTS if name not in outputs]
    if not any(runs(step, "npm run release:plan") for step in steps(plan)):
        found.append("job plan lacks the step: run: npm run release:plan")

    for name, job in listed.items():
        if name != "plan":
            if RELEASE_GATE not in condition(job):
                found.append(f"job {name} must run only if {RELEASE_GATE}")
            if "plan" not in as_list(job.get("needs")):
                found.append(f"job {name} must need plan")
        if name not in ("plan", "publish") and grants_write(job):
            found.append(f"job {name} must not grant write permissions; only plan and publish may")
        for step in steps(job):
            if uses(step, "jdx/mise-action") and with_value(step, "install_args") is None:
                found.append(f"job {name} installs all tools; mise-action needs install_args")
            if name != "plan" and uses(step, "actions/checkout"):
                if with_value(step, "ref") != SOURCE_REF:
                    found.append(f"job {name} must check out ref {SOURCE_REF}")
            if uses(step, "actions/checkout") and flag(with_value(step, "persist-credentials")) != "false":
                found.append(f"job {name} must check out with persist-credentials: false")

    if "publish" in listed:
        needed = as_list(publish.get("needs"))
        for name in (name for name in listed if name != "publish"):
            if name not in needed:
                found.append(f"job publish must need {name}")
            if name != "plan" and f"needs.{name}.result == 'success'" not in condition(publish):
                found.append(f"job publish must run only if needs.{name}.result == 'success'")
        last = steps(publish)[-1:] or [{}]
        if not runs(last[0], "npm run release"):
            found.append("job publish must end with the step: run: npm run release")
    if not any(please_behave(step, "release") for name in others for step in steps(listed[name])):
        found.append("a job publish waits on must use please-behave/action with execution-point: release")
    return sorted(set(found), key=found.index) + common(document)


def main():
    return run(sys.argv, "release.yml", violations)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
