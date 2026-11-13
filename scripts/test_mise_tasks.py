"""Tool and task detection, snapshots and technical failures of the shared mise.toml check."""
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

def write_context(directory, point, **fields):
    path = Path(directory) / f"context-{point}.json"
    path.write_text(json.dumps(dict(execution_point=point, **fields)))
    return str(path)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mise-tasks.py"
spec = importlib.util.spec_from_file_location("mise_tasks", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GOVERNOR = "github:please-behave/cli"
VALID = f'''[tools]
"{GOVERNOR}" = "0.9.0"

[tasks.format]
run = "cargo fmt"

[tasks.verify]
run = "echo not implemented"

[tasks."ci:prepare"]
run = ["npm ci"]
'''


def violations(text, tools=(GOVERNOR,), tasks=("format", "verify")):
    return mod.violations(tomllib.loads(text), list(tools), list(tasks))


class DetectionTests(unittest.TestCase):
    def test_valid_file_passes(self):
        self.assertEqual(violations(VALID), [])

    def test_placeholder_shorthand_and_dependencies_count(self):
        text = VALID + '\n[tasks.release]\ndepends = ["verify"]\n'
        self.assertEqual(violations(text, tasks=("release",)), [])
        self.assertEqual(violations('[tasks]\nformat = "cargo fmt"\n', tools=(), tasks=("format",)), [])

    def test_missing_or_empty_entries_are_reported(self):
        cases = {
            "": 3,
            VALID.replace(GOVERNOR, "other"): 1,
            VALID.replace('[tasks.format]\nrun = "cargo fmt"\n', ""): 1,
            VALID.replace('run = "cargo fmt"', 'run = ""'): 1,
            VALID.replace('run = "cargo fmt"', "description = 'x'"): 1,
            VALID.replace('run = "cargo fmt"', "run = []"): 1,
            '[tools]\n[tasks]\n': 3,
        }
        for text, count in cases.items():
            with self.subTest(text=text):
                self.assertEqual(len(violations(text)), count)

    def test_arguments(self):
        self.assertEqual(mod.parse_arguments(["x", "ctx", "--tools", "a,b", "--tasks", "c"]), ("ctx", ["a", "b"], ["c"]))
        self.assertEqual(mod.parse_arguments(["x", "ctx"]), ("ctx", [], []))
        for bad in (["x"], ["x", "ctx", "--tools"], ["x", "ctx", "--other", "a"]):
            with self.subTest(argv=bad):
                with self.assertRaises(ValueError):
                    mod.parse_arguments(bad)


class CommandTests(unittest.TestCase):
    def run_check(self, point, content, *arguments, commit=True):
        with tempfile.TemporaryDirectory(prefix="mise-tasks-") as temporary:
            repo = Path(temporary)
            for args in (["init", "--quiet"], ["config", "user.name", "T"], ["config", "user.email", "t@example.invalid"],
                         ["config", "commit.gpgsign", "false"]):
                subprocess.run(["git", *args], cwd=repo, check=True)
            if content is not None:
                (repo / "mise.toml").write_text(content)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            if commit:
                subprocess.run(["git", "commit", "--quiet", "--allow-empty", "-m", "test: record"], cwd=repo, check=True)
            context = write_context(temporary, point)
            return subprocess.run([sys.executable, "-B", str(SCRIPT), context, *arguments], cwd=repo,
                                  capture_output=True, text=True)

    def test_verdicts(self):
        arguments = ("--tools", GOVERNOR, "--tasks", "format,verify")
        for point in ("pre-commit", "check", "pre-push"):
            with self.subTest(point=point):
                self.assertEqual(self.run_check(point, VALID, *arguments).returncode, 0)
        missing = self.run_check("check", None, *arguments)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("missing", missing.stdout)
        incomplete = self.run_check("pre-push", "[tools]\n", *arguments)
        self.assertEqual(incomplete.returncode, 1)
        self.assertIn("format", incomplete.stdout)

    def test_pre_push_reads_head_and_check_reads_working_tree(self):
        with tempfile.TemporaryDirectory(prefix="mise-tasks-") as temporary:
            repo = Path(temporary)
            for args in (["init", "--quiet"], ["config", "user.name", "T"], ["config", "user.email", "t@example.invalid"],
                         ["config", "commit.gpgsign", "false"]):
                subprocess.run(["git", *args], cwd=repo, check=True)
            (repo / "mise.toml").write_text(VALID)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "test: record"], cwd=repo, check=True)
            (repo / "mise.toml").write_text("[tools]\n")
            results = {}
            for point in ("check", "pre-push"):
                context = write_context(temporary, point)
                results[point] = subprocess.run([sys.executable, "-B", str(SCRIPT), context, "--tasks", "format"],
                                                cwd=repo, capture_output=True, text=True).returncode
            self.assertEqual(results, {"check": 1, "pre-push": 0})

    def test_technical_failures_are_errors(self):
        self.assertEqual(self.run_check("commit-msg", VALID, "--tasks", "format").returncode, 2)
        self.assertEqual(self.run_check("check", "not = [valid", "--tasks", "format").returncode, 2)
        self.assertEqual(self.run_check("check", VALID, "--unknown", "x").returncode, 2)


if __name__ == "__main__":
    unittest.main()
