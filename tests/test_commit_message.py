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
    shutil.copytree(ROOT / "rulesets", source / "rulesets")
    shutil.copytree(ROOT / "scripts", source / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}
    env.update(XDG_CACHE_HOME=str(root / "cache"), NO_COLOR="1", GEMINI_API_KEY="synthetic-key",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
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
        'path = "rulesets/multi-point/repository-conventions"\nref = "main"\n'
        '[imports.rule_parameters.commit-message]\nscopes_file = ".commit-scopes"\n'
        '[imports.rule_parameters.agents-size]\nmax_tokens = "1500"\n')
    # Provider packages are imported independently and execute from the cache.
    shutil.copytree(ROOT / "providers", source / "providers")
    package = source / "providers/gemini-flash-lite/provider.toml"
    package.write_text(package.read_text().replace('args = ["@provider/adapter.py"]',
                                                  'args = ["@source/tests/fake-gemini.py"]'))
    (source / "tests").mkdir()
    (source / "tests/fake-gemini.py").write_text(r'''import importlib.util, json, os, pathlib, sys
from unittest.mock import MagicMock, patch
adapter = pathlib.Path(__file__).resolve().parents[1] / 'providers/gemini-flash-lite/adapter.py'
spec = importlib.util.spec_from_file_location('gemini', adapter)
gemini = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gemini)
request = json.load(sys.stdin)
assert request['head'] is None
assert request['input']['manifest'] == []
assert request['input']['excerpts'] == []
assert request['input']['diff'] == ''
assert 'BODY MUST NEVER REACH' not in json.dumps(request)
assert all(r['input'] == 'commit-header' and r['parameters']['model'] == 'gemini-3.5-flash-lite' for r in request['reviews'])
mode = os.environ.get('COMMIT_REVIEW_TEST_MODE', 'PASS')
finding = {'source': 'commit-header', 'path': None, 'line': 1, 'message': 'Header wording evaluated'}
if mode == 'file-evidence':
    finding = {'path': '.commit-scopes', 'line': 1, 'message': 'Wrong evidence source'}
status = mode if mode in ('PASS', 'FAIL', 'ERROR') else 'PASS'
verdict = {'reviews': [{'id': r['id'], 'status': status, 'reason': 'Header wording evaluated', 'findings': [] if status == 'ERROR' else [finding]} for r in request['reviews']]}
envelope = {'candidates': [{'finishReason': 'MAX_TOKENS' if mode == 'truncated' else 'STOP', 'content': {'parts': [{'text': json.dumps(verdict)}]}}]}
response = MagicMock()
response.__enter__.return_value = response
response.status = 200
response.read.return_value = json.dumps(envelope).encode()
class Opener:
    def open(self, http_request, timeout):
        assert '/models/gemini-3.5-flash-lite:generateContent' in http_request.full_url
        payload = json.loads(http_request.data)
        assert payload['contents'][0]['parts'][0]['text'] == request['prompt']
        assert payload['generationConfig']['responseJsonSchema'] == request['response_schema']
        with pathlib.Path('.git/provider-calls').open('a') as calls:
            calls.write('mock HTTP request\n')
        return response
with patch.object(gemini, 'build_opener', return_value=Opener()):
    print(json.dumps(gemini.review(request)))
''')
    git(source, "add", ".")
    git(source, "commit", "--quiet", "-m", "test: add provider package and mock HTTP transport")
    with (consumer / ".please/config.toml").open("a") as config:
        config.write('\n[[provider_imports]]\nid = "gemini-flash-lite"\ngit = ' + json.dumps(str(source)) +
                     '\npath = "providers/gemini-flash-lite"\nref = "main"\n')
    run([str(executable), "sync", "--yes"], cwd=consumer, env=env)
    assert not (consumer / ".please/providers/gemini-flash-lite.toml").exists()
    assert not (consumer / ".please/adapters").exists()
    # Hook execution must reuse the cache after the source becomes unavailable.
    source.rename(root / "offline-source")
    git(consumer, "add", ".")
    git(consumer, "commit", "--quiet", "-m", "feat(cli): add command", "-m", "BODY MUST NEVER REACH")
    head = git(consumer, "rev-parse", "HEAD").stdout.strip()
    calls = consumer / ".git/provider-calls"
    assert len(calls.read_text().splitlines()) == 1
    for message in ["unknown: reject commit", "fix(other): reject scope"]:
        git(consumer, "commit", "--allow-empty", "-m", message, expected=1)
        assert git(consumer, "rev-parse", "HEAD").stdout.strip() == head
    report = json.loads((consumer / ".please/reports/last.json").read_text())
    assert report["overall"] == "FAIL"
    assert len(report["results"]) == 2
    assert report["results"][0]["id"].endswith(":commit-message")
    assert report["results"][1]["status"] == "NOT_RUN"
    review_rule, = [r for r in report["plan"]["scheduled"] if r["kind"] == "review"]
    assert review_rule["provider_origin"]["path"] == "providers/gemini-flash-lite"
    assert len(calls.read_text().splitlines()) == 1  # Syntax failures make no HTTP request.
    # Advisory Review failures retain their verdict without blocking Git.
    for mode in ["FAIL", "ERROR", "file-evidence", "truncated"]:
        env["COMMIT_REVIEW_TEST_MODE"] = mode
        git(consumer, "commit", "--allow-empty", "-m", "fix: fix stuff")
        next_head = git(consumer, "rev-parse", "HEAD").stdout.strip()
        assert next_head != head
        head = next_head
        report = json.loads((consumer / ".please/reports/last.json").read_text())
        assert report["overall"] == "PASS"
        result, = [r for r in report["results"] if r["kind"] == "review"]
        assert result["status"] == ("FAIL" if mode == "FAIL" else "ERROR")
        assert result["blocking"] is False
    previous_calls = calls.read_text()
    env.pop("GEMINI_API_KEY")
    git(consumer, "commit", "--allow-empty", "-m", "fix: preserve focus")
    assert calls.read_text() == previous_calls
    report = json.loads((consumer / ".please/reports/last.json").read_text())
    assert report["overall"] == "PASS"
    result, = [r for r in report["results"] if r["kind"] == "review"]
    assert result["status"] == "ERROR" and result["blocking"] is False
    print("Integration passed: imported checks and header Review, mock Gemini HTTP, syntax gating, PASS/FAIL/ERROR, invalid evidence, missing credentials, syntax rejection and non-blocking Review verdicts.")


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
