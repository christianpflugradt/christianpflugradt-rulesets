"""Shared helpers for structural checks of GitHub workflow files; yq converts the YAML to JSON."""
import json
from pathlib import Path
import re
import subprocess
import sys

# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def expect_steps(job_id, job, expected):
    """Report each expected (description, test) step missing after its predecessor; extra steps may interleave."""
    found, position = [], 0
    listed = steps(job)
    for description, test in expected:
        for index in range(position, len(listed)):
            if test(listed[index]):
                position = index + 1
                break
        else:
            found.append(f"job {job_id} lacks the step: {description}")
    return found


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
    from snapshot import execution_point, read_file, select_snapshot
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
