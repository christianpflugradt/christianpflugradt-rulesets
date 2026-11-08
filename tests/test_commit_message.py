"""Validate the check and optionally its Please Behave managed-hook integration."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
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
    env.update(PLEASE_GIT_HOOK="commit-msg", PLEASE_GIT_HOOK_ARG_COUNT="1",
               PLEASE_GIT_HOOK_ARG_1=str(message), PLEASE_PARAM_SCOPES_FILE=str(scopes))
    accepted = [f"{kind}: describe the change" for kind in (RULE / "commit-types.txt").read_text().splitlines()]
    accepted += ["feat(cli)!: change behavior", "fix!: change behavior", "docs: explain\n\nDetails."]
    rejected = ["", "\nfeat: hidden", "feat:", "feat: ", "feat: \t", "feat:no space",
                "unknown: change", "FEAT: change", "fix(other): change", "fix(): change",
                "fix(cli: change", "fix(cli)): change", "fix(cli)!!: change"]
    for code, messages in [(0, accepted), (1, rejected)]:
        for text in messages:
            message.write_text(text)
            run(["sh", str(RULE / "index.sh")], env=env, expected=code)
    message.write_text("feat(cli): add command\n")
    for key in ["PLEASE_GIT_HOOK", "PLEASE_GIT_HOOK_ARG_COUNT", "PLEASE_GIT_HOOK_ARG_1", "PLEASE_PARAM_SCOPES_FILE"]:
        invalid = dict(env)
        invalid.pop(key)
        run(["sh", str(RULE / "index.sh")], env=invalid, expected=2)
    for key in ["PLEASE_GIT_HOOK_ARG_1", "PLEASE_PARAM_SCOPES_FILE"]:
        run(["sh", str(RULE / "index.sh")], env=dict(env, **{key: str(root / "missing")}), expected=2)
    # A scanner/tool failure must not masquerade as a policy violation.
    tools = root / "tools"
    tools.mkdir()
    grep = tools / "grep"
    grep.write_text("#!/bin/sh\nexit 2\n")
    grep.chmod(0o755)
    run(["sh", str(RULE / "index.sh")], env=dict(env, PATH=str(tools) + os.pathsep + env["PATH"]), expected=2)
    print(f"Script tests passed: {len(accepted) + len(rejected)} messages, missing context/resources and tool errors.")


def integration(root, executable):
    source = root / "source"
    consumer = root / "consumer"
    source.mkdir()
    consumer.mkdir()
    shutil.copytree(ROOT / "rules", source / "rules")
    shutil.copytree(ROOT / "commit-msg", source / "commit-msg")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}
    env.update(XDG_CACHE_HOME=str(root / "cache"), NO_COLOR="1")
    binaries = root / "bin"
    binaries.mkdir()
    (binaries / "please").symlink_to(executable)
    env["PATH"] = str(binaries) + os.pathsep + env["PATH"]
    def git(path, *args, expected=0):
        return run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "-c", "commit.gpgsign=false", *args], cwd=path, env=env, expected=expected)
    for repository in [source, consumer]:
        git(repository, "init", "--quiet", "--initial-branch=main")
    git(source, "add", ".")
    git(source, "commit", "--quiet", "-m", "feat: add rule set")
    (consumer / ".please").mkdir()
    (consumer / ".commit-scopes").write_text("cli\n")
    (consumer / ".please/config.toml").write_text(
        f'project = "My_App"\n[[imports]]\ngit = {json.dumps(str(source))}\n'
        'path = "commit-msg/conventional-commits"\nref = "main"\n'
        '[imports.rule_parameters.commit-message]\nscopes_file = ".commit-scopes"\n')
    run([str(executable), "sync", "--yes"], cwd=consumer, env=env)
    # Hook execution must reuse the cache after the source becomes unavailable.
    source.rename(root / "offline-source")
    git(consumer, "add", ".")
    git(consumer, "commit", "--quiet", "-m", "feat(cli): add command")
    head = git(consumer, "rev-parse", "HEAD").stdout.strip()
    for message in ["unknown: reject commit", "fix(other): reject scope"]:
        git(consumer, "commit", "--allow-empty", "-m", message, expected=1)
        assert git(consumer, "rev-parse", "HEAD").stdout.strip() == head
    report = json.loads((consumer / ".please/reports/last.json").read_text())
    assert report["overall"] == "FAIL"
    assert len(report["results"]) == 1
    assert report["results"][0]["id"].endswith(":commit-message")
    print("Integration passed: imported shared Rule, offline hooks, accepted/rejected commits and report.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--please", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ruleset-tests-") as directory:
        root = Path(directory)
        script_tests(root)
        if args.please:
            integration(root, args.please.resolve(strict=True))


if __name__ == "__main__":
    main()
