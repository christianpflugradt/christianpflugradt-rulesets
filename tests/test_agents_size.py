"""Approximate token counting, limits, snapshots and technical failures."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import write_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "rules/checks/agents-size/check.py"
spec = importlib.util.spec_from_file_location("agents_size", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CountTests(unittest.TestCase):
    def test_words_and_punctuation_count_separately(self):
        self.assertEqual(mod.count_tokens("Use `x.y` now."), 8)
        self.assertEqual(mod.count_tokens("# Title\n\n- a, b\n"), 6)
        self.assertEqual(mod.count_tokens("  \n\t"), 0)
        self.assertEqual(mod.count_tokens("Grüße — fine"), 3)

    def test_limit_must_be_a_positive_integer(self):
        self.assertEqual(mod.parse_limit("1500"), 1500)
        for value in (None, "", "0", "-1", "1.5", "12 ", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    mod.parse_limit(value)


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agents-size-tests-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
        self.git("init", "--quiet", "--initial-branch=main")
        (self.repo / "README").write_text("Consumer\n")
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                               "-c", "commit.gpgsign=false", *args], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, check=True)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test: record")

    def run_rule(self, point="check", expected=0, limit="5"):
        arguments = [write_context(self.temp.name, point)]
        if limit is not None:
            arguments.append(limit)
        result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=self.repo, env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_limit_boundary_at_every_assigned_point(self):
        (self.repo / "AGENTS.md").write_text("one two three four five\n")
        self.commit()
        for point in ("pre-commit", "check", "pre-push"):
            with self.subTest(point=point):
                self.assertIn("5 approximate tokens (limit 5)", self.run_rule(point).stdout)
                self.assertIn("(limit 4)", self.run_rule(point, 1, "4").stdout)

    def test_absent_file_passes_without_limit_evidence(self):
        for point in ("pre-commit", "check", "pre-push"):
            with self.subTest(point=point):
                self.assertIn("absent", self.run_rule(point).stdout)

    def test_snapshot_follows_the_execution_point(self):
        (self.repo / "AGENTS.md").write_text("one two\n")
        self.commit()
        (self.repo / "AGENTS.md").write_text("one two three four five six seven\n")
        self.run_rule("pre-push")
        self.run_rule("check", 1)
        self.run_rule("pre-commit", 1)
        (self.repo / "AGENTS.md").write_text("one\n")
        self.git("add", ".")
        self.run_rule("pre-commit")

    def test_file_added_only_in_worktree_is_absent_at_head(self):
        (self.repo / "AGENTS.md").write_text("one two three four five six seven\n")
        self.assertIn("absent", self.run_rule("pre-push").stdout)
        self.run_rule("check", 1)

    def test_technical_failures_are_errors(self):
        (self.repo / "AGENTS.md").write_bytes(b"\xff\xfe")
        for limit in (None, "0", "many"):
            with self.subTest(limit=limit):
                self.run_rule(limit=limit, expected=2)
        self.run_rule(expected=2)
        (self.repo / "AGENTS.md").unlink()
        (self.repo / "AGENTS.md").symlink_to("README")
        self.run_rule(expected=2)

    def test_custom_points_are_unsupported(self):
        self.run_rule("release", 2)


if __name__ == "__main__":
    unittest.main()
