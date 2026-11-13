"""Require the shared structure of ci.yml; runners, matrices, timeouts' values and extra steps stay with consumers."""
from pathlib import Path
import sys

# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))


def violations(document):
    import workflow
    found = []
    if document.get("name") != "CI":
        found.append('name must be "CI"')
    events = workflow.triggers(document)
    push = workflow.as_dict(events.get("push"))
    if "main" not in workflow.as_list(push.get("branches")):
        found.append("must run on push to main")
    if "pull_request" not in events:
        found.append("must run on pull_request")
    job = workflow.jobs(document).get("check")
    if job is None:
        found.append("job check is missing")
    else:
        found += workflow.expect_steps("check", job, [
            ("actions/checkout with persist-credentials: false",
             lambda s: workflow.uses(s, "actions/checkout") and workflow.flag(workflow.with_value(s, "persist-credentials")) == "false"),
            ("jdx/mise-action without install_args",
             lambda s: workflow.uses(s, "jdx/mise-action") and workflow.with_value(s, "install_args") is None),
            ("run: mise run prepare", lambda s: workflow.runs(s, "mise run prepare")),
            ("please-behave/action with execution-point: check, install: false and sync: true",
             lambda s: workflow.please_behave(s, "check")
             and workflow.flag(workflow.with_value(s, "install")) == "false"
             and workflow.flag(workflow.with_value(s, "sync")) == "true"),
        ])
    return found + workflow.common(document)


def main():
    import workflow
    return workflow.run(sys.argv, "ci.yml", violations)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
