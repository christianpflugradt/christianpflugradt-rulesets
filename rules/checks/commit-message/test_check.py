"""Validate the commit-message check."""
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

def write_context(directory, point, **fields):
    path = Path(directory) / f"context-{point}.json"
    path.write_text(json.dumps(dict(execution_point=point, **fields)))
    return str(path)

ROOT = Path(__file__).resolve().parents[3]
RULE = ROOT / "rules/checks/commit-message"


def run(args, *, cwd=None, env=None, expected=0):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
    return result


def script_tests(root):
    message = root / "commit message.txt"
    scopes = root / "allowed scopes.txt"
    scopes.write_text("cli\nconfig\ndocs\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}

    def check(expected, point="commit-msg", context=None, scopes_file=scopes):
        context = context or write_context(root, point, commit_message=dict(file=str(message)))
        return run([sys.executable, str(RULE / "check.py"), context, str(scopes_file)], env=env, expected=expected)

    accepted = [f"{kind}: describe the change" for kind in (RULE / "commit-types.txt").read_text().splitlines()]
    accepted += ["feat(cli)!: change behavior", "fix!: change behavior", "docs: explain\n\nDetails."]
    rejected = ["", "\nfeat: hidden", "feat:", "feat: ", "feat: \t", "feat:no space",
                "unknown: change", "FEAT: change", "fix(other): change", "fix(): change",
                "fix(cli: change", "fix(cli)): change", "fix(cli)!!: change"]
    for code, messages in [(0, accepted), (1, rejected)]:
        for text in messages:
            message.write_text(text)
            check(code)
    message.write_text("feat(cli): add command\n")
    check(2, point="pre-commit")
    check(2, scopes_file=root / "missing")
    check(2, context=write_context(root, "commit-msg", commit_message=dict(file=str(root / "missing"))))
    check(2, context=write_context(root, "commit-msg"))
    check(2, context=str(root / "missing.json"))
    run([sys.executable, str(RULE / "check.py")], env=env, expected=2)
    print(f"Script tests passed: {len(accepted) + len(rejected)} messages and missing context/resources.")


def main():
    with tempfile.TemporaryDirectory(prefix="ruleset-tests-") as directory:
        root = Path(directory)
        script_tests(root)


if __name__ == "__main__":
    main()
