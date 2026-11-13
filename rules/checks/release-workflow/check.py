"""Require the shared structure of release.yml; scripts, artifacts and candidate steps stay with consumers."""
from pathlib import Path
import sys

# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

REQUIRED_JOBS = ("plan", "release-readiness", "release-candidate", "publish")
REQUIRED_OUTPUTS = ("release", "version", "source_sha")
RELEASE_GATE = "needs.plan.outputs.release == 'true'"
SOURCE_REF = "${{ needs.plan.outputs.source_sha }}"


def condition(job):
    return " ".join(str(job.get("if", "")).split())


def violations(document):
    import workflow
    found = []
    if document.get("name") != "Release":
        found.append('name must be "Release"')
    events = set(workflow.triggers(document))
    if "workflow_dispatch" not in events or events - {"workflow_dispatch", "schedule"}:
        found.append("must be triggered by workflow_dispatch, optionally also by schedule")
    concurrency = workflow.as_dict(document.get("concurrency"))
    if concurrency.get("group") != "release-main" or workflow.flag(concurrency.get("cancel-in-progress")) != "false":
        found.append("concurrency must use group release-main with cancel-in-progress: false")
    if workflow.flag(workflow.as_dict(document.get("env")).get("MISE_AUTO_INSTALL")) != "false":
        found.append("env must set MISE_AUTO_INSTALL to 'false' so jobs keep their explicit tool subsets")

    listed = workflow.jobs(document)
    found += [f"job {name} is missing" for name in REQUIRED_JOBS if name not in listed]
    plan, publish = listed.get("plan", {}), listed.get("publish", {})
    others = [name for name in listed if name not in ("plan", "publish")]

    if "github.ref == 'refs/heads/main'" not in condition(plan):
        found.append("job plan must run only on refs/heads/main")
    outputs = workflow.as_dict(plan.get("outputs"))
    found += [f"job plan lacks the output {name}" for name in REQUIRED_OUTPUTS if name not in outputs]
    if not any(workflow.runs(step, "npm run release:plan") for step in workflow.steps(plan)):
        found.append("job plan lacks the step: run: npm run release:plan")

    for name, job in listed.items():
        if name != "plan":
            if RELEASE_GATE not in condition(job):
                found.append(f"job {name} must run only if {RELEASE_GATE}")
            if "plan" not in workflow.as_list(job.get("needs")):
                found.append(f"job {name} must need plan")
        if name not in ("plan", "publish") and workflow.grants_write(job):
            found.append(f"job {name} must not grant write permissions; only plan and publish may")
        for step in workflow.steps(job):
            if workflow.uses(step, "jdx/mise-action") and workflow.with_value(step, "install_args") is None:
                found.append(f"job {name} installs all tools; mise-action needs install_args")
            if name != "plan" and workflow.uses(step, "actions/checkout"):
                if workflow.with_value(step, "ref") != SOURCE_REF:
                    found.append(f"job {name} must check out ref {SOURCE_REF}")
            if workflow.uses(step, "actions/checkout") and workflow.flag(workflow.with_value(step, "persist-credentials")) != "false":
                found.append(f"job {name} must check out with persist-credentials: false")

    if "publish" in listed:
        needed = workflow.as_list(publish.get("needs"))
        for name in (name for name in listed if name != "publish"):
            if name not in needed:
                found.append(f"job publish must need {name}")
            if name != "plan" and f"needs.{name}.result == 'success'" not in condition(publish):
                found.append(f"job publish must run only if needs.{name}.result == 'success'")
        last = workflow.steps(publish)[-1:] or [{}]
        if not workflow.runs(last[0], "npm run release"):
            found.append("job publish must end with the step: run: npm run release")
    if not any(workflow.please_behave(step, "release") for name in others for step in workflow.steps(listed[name])):
        found.append("a job publish waits on must use please-behave/action with execution-point: release")
    return sorted(set(found), key=found.index) + workflow.common(document)


def main():
    import workflow
    return workflow.run(sys.argv, "release.yml", violations)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
