"""Structure detection, snapshots and technical failures of the shared CI and Release workflow rules."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import write_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
CI = ROOT / "rules/checks/ci-workflow/check.py"
RELEASE = ROOT / "rules/checks/release-workflow/check.py"
SHA = "a" * 40


def load(path):
    spec = importlib.util.spec_from_file_location(path.parent.name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CI_YAML = f'''name: CI
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  check:
    name: Check
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@{SHA} # v7
        with:
          persist-credentials: false
      - uses: jdx/mise-action@{SHA} # v5
      - run: apt-get update
      - run: mise run prepare
      - uses: please-behave/action@{SHA} # v1
        with:
          install: 'false'
          sync: 'true'
          execution-point: check
'''

RELEASE_YAML = f'''name: Release
on:
  workflow_dispatch:
  schedule:
    - cron: '0 3 * * 1'
permissions:
  contents: read
concurrency:
  group: release-main
  cancel-in-progress: false
env:
  MISE_AUTO_INSTALL: 'false'
jobs:
  plan:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: write
    outputs:
      release: ${{{{ steps.plan.outputs.release }}}}
      version: ${{{{ steps.plan.outputs.version }}}}
      source_sha: ${{{{ steps.plan.outputs.source_sha }}}}
    steps:
      - uses: actions/checkout@{SHA} # v7
        with:
          persist-credentials: false
      - uses: jdx/mise-action@{SHA} # v5
        with:
          install_args: node
      - id: plan
        run: npm run release:plan
  release-readiness:
    needs: plan
    if: needs.plan.outputs.release == 'true'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@{SHA} # v7
        with:
          ref: ${{{{ needs.plan.outputs.source_sha }}}}
          persist-credentials: false
      - uses: jdx/mise-action@{SHA} # v5
        with:
          install_args: python
  release-candidate:
    needs: plan
    if: needs.plan.outputs.release == 'true'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: please-behave/action@{SHA} # v1
        with:
          execution-point: release
  publish:
    needs: [plan, release-readiness, release-candidate]
    if: >-
      needs.plan.outputs.release == 'true' &&
      needs.release-readiness.result == 'success' &&
      needs.release-candidate.result == 'success'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: write
      packages: write
    steps:
      - run: npm run release
'''


def replaced(text, old, new):
    assert old in text
    return text.replace(old, new, 1)


@unittest.skipUnless(shutil.which("yq"), "yq required")
class StructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import workflow
        cls.parse = staticmethod(workflow.parse)
        cls.ci, cls.release = staticmethod(load(CI).violations), staticmethod(load(RELEASE).violations)

    def test_valid_workflows_pass(self):
        self.assertEqual(self.ci(self.parse(CI_YAML.encode())), [])
        self.assertEqual(self.release(self.parse(RELEASE_YAML.encode())), [])

    def test_ci_deviations_are_reported(self):
        cases = {
            "name: CI": "name: Build",
            "branches: [main]": "branches: [dev]",
            "  pull_request:\n": "",
            "    timeout-minutes: 10\n": "",
            "      - run: mise run prepare\n": "",
            "          persist-credentials: false\n": "          fetch-depth: 0\n",
            "          sync: 'true'": "          sync: 'false'",
            "  contents: read": "  contents: write",
            f"actions/checkout@{SHA}": "actions/checkout@v7",
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                self.assertEqual(len(self.ci(self.parse(replaced(CI_YAML, old, new).encode()))), 1)

    def test_ci_step_order_matters_but_extra_steps_are_allowed(self):
        swapped = replaced(CI_YAML, "      - run: apt-get update\n      - run: mise run prepare\n",
                           "      - run: mise run prepare\n      - run: apt-get update\n")
        self.assertEqual(self.ci(self.parse(swapped.encode())), [])
        early = replaced(CI_YAML, "      - run: mise run prepare\n", "")
        early = replaced(early, "      - uses: jdx", f"      - run: mise run prepare\n      - uses: jdx")
        self.assertEqual(len(self.ci(self.parse(early.encode()))), 1)

    def test_shorthand_triggers_are_understood(self):
        text = replaced(CI_YAML, "on:\n  push:\n    branches: [main]\n  pull_request:\n", "on: [pull_request]\n")
        self.assertEqual(len(self.ci(self.parse(text.encode()))), 1)

    def test_release_deviations_are_reported(self):
        cases = {
            "name: Release": "name: Ship",
            "  workflow_dispatch:\n": "  workflow_dispatch:\n  push:\n",
            "cancel-in-progress: false": "cancel-in-progress: true",
            "  MISE_AUTO_INSTALL: 'false'": "  MISE_AUTO_INSTALL: 'true'",
            "    if: github.ref == 'refs/heads/main'\n": "",
            "      source_sha:": "      sha:",
            "        run: npm run release:plan": "        run: npm run plan",
            "    needs: plan\n    if: needs.plan.outputs.release == 'true'\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    steps:\n      - uses: please":
                "    if: needs.plan.outputs.release == 'true'\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    steps:\n      - uses: please",
            "          install_args: python\n": "          fetch: no\n",
            "          ref: ${{ needs.plan.outputs.source_sha }}\n": "          ref: ${{ github.sha }}\n",
            "      needs.release-candidate.result == 'success'": "      true",
            "needs: [plan, release-readiness, release-candidate]": "needs: [plan, release-readiness]",
            "      - run: npm run release\n": "      - run: npm run release\n      - run: echo done\n",
            "execution-point: release": "execution-point: check",
        }
        for old, new in cases.items():
            with self.subTest(old=old):
                self.assertTrue(self.release(self.parse(replaced(RELEASE_YAML, old, new).encode())))

    def test_write_permission_is_limited_to_plan_and_publish(self):
        text = replaced(RELEASE_YAML, "    needs: plan\n    if: needs.plan.outputs.release == 'true'\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    steps:\n      - uses: please",
                        "    needs: plan\n    if: needs.plan.outputs.release == 'true'\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    permissions:\n      packages: write\n    steps:\n      - uses: please")
        self.assertEqual(len(self.release(self.parse(text.encode()))), 1)

    def test_extra_jobs_must_gate_and_be_awaited(self):
        extra = ("  smoke:\n    needs: [plan, release-candidate]\n    if: needs.plan.outputs.release == 'true'\n"
                 "    runs-on: ubuntu-24.04\n    timeout-minutes: 10\n    steps:\n      - run: echo smoke\n")
        text = replaced(RELEASE_YAML, "  publish:\n", extra + "  publish:\n")
        self.assertEqual(len(self.release(self.parse(text.encode()))), 2)
        text = replaced(text, "needs: [plan, release-readiness, release-candidate]", "needs: [plan, release-readiness, release-candidate, smoke]")
        text = replaced(text, "      needs.release-candidate.result == 'success'", "      needs.release-candidate.result == 'success' &&\n      needs.smoke.result == 'success'")
        self.assertEqual(self.release(self.parse(text.encode())), [])

    def test_unpinned_actions_and_missing_timeouts_are_reported_in_both(self):
        self.assertEqual(len(self.release(self.parse(replaced(RELEASE_YAML, f"please-behave/action@{SHA}", "please-behave/action@v1").encode()))), 1)
        self.assertEqual(len(self.release(self.parse(replaced(RELEASE_YAML, "    timeout-minutes: 10\n    permissions:\n      contents: write\n      packages", "    permissions:\n      contents: write\n      packages").encode()))), 1)
        local = replaced(CI_YAML, f"      - uses: please-behave/action@{SHA} # v1", "      - uses: ./")
        self.assertEqual(len(self.ci(self.parse(local.encode()))), 1)  # only the missing step, no pinning finding


@unittest.skipUnless(shutil.which("yq"), "yq required")
class CommandTests(unittest.TestCase):
    def repo(self, temporary, name, content):
        repo = Path(temporary)
        for args in (["init", "--quiet"], ["config", "user.name", "T"], ["config", "user.email", "t@example.invalid"],
                     ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git", *args], cwd=repo, check=True)
        if content is not None:
            (repo / ".github/workflows").mkdir(parents=True)
            (repo / ".github/workflows" / name).write_text(content)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "--quiet", "--allow-empty", "-m", "test: record"], cwd=repo, check=True)
        return repo

    def run_check(self, script, point, repo, temporary):
        context = write_context(temporary, point)
        return subprocess.run([sys.executable, "-B", str(script), context], cwd=repo, capture_output=True, text=True)

    def test_verdicts_and_snapshots(self):
        for script, name, valid in ((CI, "ci.yml", CI_YAML), (RELEASE, "release.yml", RELEASE_YAML)):
            with self.subTest(rule=name), tempfile.TemporaryDirectory(prefix="workflow-rules-") as temporary:
                repo = self.repo(temporary, name, valid)
                for point in ("check", "pre-push"):
                    self.assertEqual(self.run_check(script, point, repo, temporary).returncode, 0)
                (repo / ".github/workflows" / name).write_text("name: Other\n")
                results = {point: self.run_check(script, point, repo, temporary).returncode for point in ("check", "pre-push")}
                self.assertEqual(results, {"check": 1, "pre-push": 0})

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory(prefix="workflow-rules-") as temporary:
            repo = self.repo(temporary, "ci.yml", None)
            result = self.run_check(CI, "check", repo, temporary)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing", result.stdout)

    def test_technical_failures_are_errors(self):
        with tempfile.TemporaryDirectory(prefix="workflow-rules-") as temporary:
            repo = self.repo(temporary, "ci.yml", "name: [unclosed\n")
            self.assertEqual(self.run_check(CI, "check", repo, temporary).returncode, 2)
            self.assertEqual(self.run_check(CI, "commit-msg", repo, temporary).returncode, 2)
            (repo / ".github/workflows/ci.yml").write_text("- a list\n")
            self.assertEqual(self.run_check(CI, "check", repo, temporary).returncode, 2)

    def test_missing_yq_is_an_error(self):
        with tempfile.TemporaryDirectory(prefix="workflow-rules-") as temporary:
            repo = self.repo(temporary, "ci.yml", CI_YAML)
            context = write_context(temporary, "check")
            result = subprocess.run([sys.executable, "-B", str(CI), context], cwd=repo, capture_output=True, text=True,
                                    env={"PATH": str(Path(sys.executable).parent)})
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
