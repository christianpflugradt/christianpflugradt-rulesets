"""Exact license matching and technical failures of the license check."""
import json
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

def write_context(directory, point, **fields):
    path = Path(directory) / f"context-{point}.json"
    path.write_text(json.dumps(dict(execution_point=point, **fields)))
    return str(path)

ROOT = Path(__file__).resolve().parents[3]
RULE = ROOT / "rules/checks/license"
SCRIPT = RULE / "check.py"
spec = importlib.util.spec_from_file_location("license_check", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="license-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "consumer"
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}
        self.env.update(XDG_CACHE_HOME=str(self.base / "cache"), NO_COLOR="1")
        self.git("init", "--quiet", "--initial-branch=main")
        (self.repo / "README").write_text("Consumer\n")
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                               "-c", "commit.gpgsign=false", *args], cwd=self.repo,
                              env=self.env, capture_output=True, text=True, check=True)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test: record license")

    def rule(self, point="check", expected=0, target="LICENSE", licenses=None, **env):
        result = subprocess.run([sys.executable, str(SCRIPT), write_context(self.base, point), target,
                                 str(RULE / "licenses" if licenses is None else licenses)], cwd=self.repo,
                                env=dict(self.env, **env), capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertIn({0: "PASS:", 1: "FAIL:", 2: "ERROR:"}[expected], result.stdout + result.stderr)
        return result

    def test_all_permitted_licenses_match_at_both_points(self):
        for name in ("Apache-2.0", "PolyForm-Noncommercial-1.0.0", "Unlicense"):
            with self.subTest(license=name):
                shutil.copyfile(RULE / "licenses" / (name + ".txt"), self.repo / "LICENSE")
                self.commit()
                self.assertIn(name, self.rule().stdout)
                self.assertIn(name, self.rule("pre-push").stdout)

    def test_byte_differences_fail_at_both_points(self):
        content = (RULE / "licenses/Unlicense.txt").read_bytes()
        for altered in (b"invalid license\n", content + b"\n", content.replace(b"\n", b"\r\n")):
            with self.subTest(content=altered[:20]):
                (self.repo / "LICENSE").write_bytes(altered)
                self.commit()
                self.rule(expected=1)
                self.rule("pre-push", 1)

    def test_missing_files_fail_at_both_points(self):
        self.rule(expected=1)
        self.rule("pre-push", 1)

    def test_pre_push_reads_head_instead_of_worktree_or_index(self):
        shutil.copyfile(RULE / "licenses/Unlicense.txt", self.repo / "LICENSE")
        self.commit()
        (self.repo / "LICENSE").write_text("invalid staged license")
        self.git("add", "LICENSE")
        (self.repo / "LICENSE").unlink()
        self.rule(expected=1)
        self.rule("pre-push")

    def test_nonregular_consumer_files_fail(self):
        (self.repo / "LICENSE").symlink_to(RULE / "licenses/Unlicense.txt")
        self.commit()
        self.rule(expected=1)
        self.rule("pre-push", 1)

    def test_bad_context_and_missing_references_are_errors(self):
        self.rule("unsupported", 2)
        self.rule("release", 2)
        for extra in ({"target": ""}, {"target": "../LICENSE"}, {"target": "/LICENSE"}):
            with self.subTest(extra=extra):
                self.rule(expected=2, **extra)
        (self.base / "licenses").mkdir()
        (self.base / "licenses/.hidden").write_text("not a reference")
        (self.base / "licenses/link").symlink_to(RULE / "licenses/Unlicense.txt")
        self.rule(expected=2, licenses=self.base / "licenses")

    def test_git_failures_are_errors(self):
        self.rule("pre-push", 2, PATH=str(self.base))
        shutil.rmtree(self.repo / ".git")
        self.rule("pre-push", 2)
        self.git("init", "--quiet")
        self.rule("pre-push", 2)  # Unborn HEAD is a technical failure, not a missing license.

    def test_io_and_git_read_errors_are_errors(self):
        argv = ["check.py", write_context(self.base, "check"), "LICENSE", str(RULE / "licenses")]
        pushed = [argv[0], write_context(self.base, "pre-push"), *argv[2:]]
        with patch.object(sys, "argv", argv), patch("sys.stderr", new_callable=io.StringIO):
            with patch.object(Path, "iterdir", side_effect=PermissionError("unreadable references")):
                self.assertEqual(mod.main(), 2)
            with patch.object(Path, "read_bytes", side_effect=PermissionError("unreadable license")):
                with patch.object(Path, "lstat", return_value=os.stat(SCRIPT)):
                    self.assertEqual(mod.main(), 2)
            with patch.object(sys, "argv", pushed):
                listing = subprocess.CompletedProcess([], 0, b"100644 blob abc\tLICENSE\0", b"")
                failure = subprocess.CompletedProcess([], 128, b"", b"cannot read blob")
                with patch.object(subprocess, "run", side_effect=[listing, failure]):
                    self.assertEqual(mod.main(), 2)


if __name__ == "__main__":
    unittest.main()
