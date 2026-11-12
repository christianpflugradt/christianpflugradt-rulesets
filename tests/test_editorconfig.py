"""Baseline detection, snapshots and technical failures of the editorconfig check."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import write_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "rules/checks/editorconfig/check.py"
spec = importlib.util.spec_from_file_location("editorconfig", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BASELINE = (ROOT / ".editorconfig").read_text()


class BaselineTests(unittest.TestCase):
    def test_repository_file_and_extensions_pass(self):
        self.assertEqual(mod.violations(BASELINE), [])
        extended = BASELINE.replace("[*]\n", "[*]\nmax_line_length = 140\n") + "\n[*.{rs,py}]\nindent_size = 4\n"
        self.assertEqual(mod.violations(extended), [])

    def test_case_comments_and_spacing_are_tolerated(self):
        text = "; c\nROOT=True\n[*]\nCharset = UTF-8\nend_of_line=lf\ninsert_final_newline = true\n" \
               "trim_trailing_whitespace = true\nindent_style = space\nindent_size = 2\n" \
               "[*.md]\ntrim_trailing_whitespace = false\n[Makefile]\nindent_style = tab\n"
        self.assertEqual(mod.violations(text), [])

    def test_deviations_are_reported(self):
        cases = {
            "root = true\n": 3,
            BASELINE.replace("root = true", "root = false"): 1,
            BASELINE.replace("indent_size = 2", "indent_size = 4"): 1,
            BASELINE.replace("indent_size = 2\n", ""): 1,
            BASELINE.replace("[*.md]", "[*.txt]"): 1,
            BASELINE.replace("indent_style = tab", "indent_style = space"): 1,
        }
        for text, count in cases.items():
            with self.subTest(text=text):
                self.assertEqual(len(mod.violations(text)), count)


class CommandTests(unittest.TestCase):
    def run_check(self, point, content):
        with tempfile.TemporaryDirectory(prefix="editorconfig-") as temporary:
            repo = Path(temporary)
            for args in (["init", "--quiet"], ["config", "user.name", "T"], ["config", "user.email", "t@example.invalid"],
                         ["config", "commit.gpgsign", "false"]):
                subprocess.run(["git", *args], cwd=repo, check=True)
            if content is not None:
                (repo / ".editorconfig").write_text(content)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--quiet", "--allow-empty", "-m", "test: record"], cwd=repo, check=True)
            context = write_context(temporary, point)
            return subprocess.run([sys.executable, "-B", str(SCRIPT), context], cwd=repo, capture_output=True, text=True)

    def test_verdicts(self):
        self.assertEqual(self.run_check("pre-commit", BASELINE).returncode, 0)
        self.assertEqual(self.run_check("check", BASELINE).returncode, 0)
        self.assertEqual(self.run_check("pre-push", BASELINE).returncode, 0)
        missing = self.run_check("check", None)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("missing", missing.stdout)
        self.assertEqual(self.run_check("pre-push", "root = true\n").returncode, 1)

    def test_unsupported_point_is_error(self):
        result = self.run_check("commit-msg", BASELINE)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
