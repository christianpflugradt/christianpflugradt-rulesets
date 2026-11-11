"""Snapshot, error and optional real-tool/Please Behave integration tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLEASE = os.environ.get("PLEASE_EXECUTABLE") or shutil.which("please")
GITLEAKS = os.environ.get("GITLEAKS_EXECUTABLE") or shutil.which("gitleaks")
TOKEN = "gh" + "p_" + "0123456789abcdef" * 2 + "ABCD"


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="security-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "consumer"
        self.repo.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("PLEASE_")}
        self.env.update(PATH=str(self.bin) + os.pathsep + self.env["PATH"],
                        XDG_CACHE_HOME=str(self.base / "cache"), NO_COLOR="1")
        self.git("init", "--quiet", "--initial-branch=main")
        self.write("safe.txt", "safe contents\n")
        self.commit()
        self.fake()

    def run_command(self, args, expected=0, env=None):
        result = subprocess.run(args, cwd=self.repo, env=env or self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, (args, result.stdout, result.stderr))
        return result

    def git(self, *args):
        return self.run_command(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                 "-c", "commit.gpgsign=false", *args])

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test: record snapshot")

    def fake(self, status=0, report="[]"):
        scanner = self.bin / "gitleaks"
        scanner.write_text(f"#!{sys.executable}\n" +
            "import json,pathlib,sys\n" +
            "assert sys.argv[1] == 'dir' and sys.argv[-1] == '.'\n" +
            "assert sys.argv[sys.argv.index('--exit-code')+1] == '10'\n" +
            f"pathlib.Path({str(self.base / 'snapshot.json')!r}).write_text(json.dumps({{str(p):p.read_text() for p in pathlib.Path('.').rglob('*') if p.is_file()}}))\n" +
            (f"pathlib.Path(sys.argv[sys.argv.index('--report-path')+1]).write_text({report!r})\n" if report is not None else "") +
            "print('PRIVATE_DIAGNOSTIC', file=sys.stderr)\n" + f"sys.exit({status})\n")
        scanner.chmod(0o755)

    def rule(self, rule="secret-scan", point="check", expected=0, **extra):
        directory = ROOT / "rules/checks" / rule
        return self.run_command(["sh", str(directory / "index.sh")], expected,
            dict(self.env, PLEASE_RULE_DIRECTORY=str(directory), PLEASE_EXECUTION_POINT=point, **extra))

    def snapshot(self):
        return json.loads((self.base / "snapshot.json").read_text())

    def test_worktree_contents_include_staged_unstaged_and_nonignored_untracked(self):
        self.write("safe.txt", "staged")
        self.git("add", "safe.txt")
        self.write("safe.txt", "unstaged")
        self.write("new file\nwith newline.txt", "new")
        self.write(".gitignore", "ignored.txt\n")
        self.write("ignored.txt", "ignored")
        self.write("tracked.txt", "tracked")
        self.git("add", "-f", "tracked.txt")
        self.write(".gitignore", "ignored.txt\ntracked.txt\n")
        self.rule()
        snapshot = self.snapshot()
        self.assertEqual(snapshot["safe.txt"], "unstaged")
        self.assertEqual(snapshot["new file\nwith newline.txt"], "new")
        self.assertEqual(snapshot["tracked.txt"], "tracked")
        self.assertNotIn("ignored.txt", snapshot)
        self.assertFalse(any(".git/" in p for p in snapshot))

    def test_head_ignores_history_index_worktree_and_export_attributes(self):
        self.write("historical.txt", TOKEN)
        self.commit()
        self.git("rm", "historical.txt")
        self.write("exported.txt", "$Format:%H$")
        self.write("hidden.txt", "must scan")
        self.write(".gitattributes", "hidden.txt export-ignore\nexported.txt export-subst\n")
        self.commit()
        self.write("safe.txt", "staged")
        self.git("add", "safe.txt")
        self.write("safe.txt", "unstaged")
        self.write("untracked.txt", TOKEN)
        (self.repo / "hidden.txt").unlink()
        self.rule(point="pre-push")
        snapshot = self.snapshot()
        self.assertEqual(snapshot["safe.txt"], "safe contents\n")
        self.assertEqual(snapshot["hidden.txt"], "must scan")
        self.assertEqual(snapshot["exported.txt"], "$Format:%H$")
        self.assertNotIn("historical.txt", snapshot)
        self.assertNotIn("untracked.txt", snapshot)

    def test_deleted_and_symlink_contents_are_excluded(self):
        self.write("folder/file.txt", "contents")
        self.commit()
        (self.repo / "safe.txt").unlink()
        (self.repo / "folder/file.txt").unlink()
        (self.repo / "folder").rmdir()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "file.txt").write_text(TOKEN)
        (self.repo / "folder").symlink_to(outside, target_is_directory=True)
        (self.repo / "link").symlink_to(outside / "file.txt")
        self.rule()
        self.assertEqual(self.snapshot(), {})

    def test_symlinks_in_commit_are_not_followed(self):
        (self.repo / "link").symlink_to("safe.txt")
        self.commit()
        self.rule(point="pre-push")
        self.assertNotIn("link", self.snapshot())

    def test_submodule_and_special_entries_are_errors(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},module")
        self.git("commit", "--quiet", "-m", "test: add gitlink")
        self.rule(expected=2)  # An uninitialized submodule also blocks coverage.
        (self.repo / "module").mkdir()
        for point in ("check", "pre-push"):
            self.rule(point=point, expected=2)

    def test_missing_gitleaks_is_an_error(self):
        (self.bin / "gitleaks").unlink()
        (self.bin / "python3").symlink_to(sys.executable)
        self.env["PATH"] = str(self.bin)
        directory = ROOT / "rules/checks/secret-scan"
        self.run_command(["/bin/sh", str(directory / "index.sh")], 2,
            dict(self.env, PLEASE_RULE_DIRECTORY=str(directory), PLEASE_EXECUTION_POINT="check"))

    def test_reports_and_scanner_failures_cannot_pass(self):
        cases = [(1, "[]"), (2, "[]"), (10, "[]"), (0, None), (0, ""),
                 (0, "not json"), (0, "{}"), (0, "[1]"), (10, '[{}]'),
                 (0, '[{"File":"file","RuleID":"rule"}]')]
        for status, report in cases:
            with self.subTest(status=status, report=report):
                self.fake(status, report)
                result = self.rule(expected=2)
                self.assertNotIn("PRIVATE_DIAGNOSTIC", result.stdout + result.stderr)

    def test_findings_fail_without_disclosing_secret_values(self):
        self.fake(10, json.dumps([dict(File="file\nname", RuleID="test-rule", Secret=TOKEN, Match=TOKEN)]))
        result = self.rule(expected=1)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertIn("test-rule", result.stdout)
        self.assertIn("file\\nname", result.stdout)

    def test_filename_rules_use_worktree_or_head_and_allow_templates(self):
        self.write(".env", "local")
        self.rule("sensitive-files", expected=1)
        self.rule("sensitive-files", "pre-push")
        self.commit()
        (self.repo / ".env").unlink()
        self.rule("sensitive-files")
        self.rule("sensitive-files", "pre-push", 1)
        self.git("add", "-u")
        self.git("commit", "--quiet", "-m", "test: delete sensitive file")
        self.write(".gitignore", ".env*\n")
        self.write(".env.local", "ignored")
        self.write(".env.example", "template")
        self.rule("sensitive-files")
        self.git("add", "-f", ".env.local")
        self.rule("sensitive-files", expected=1)

    def test_custom_points_require_explicit_compatible_snapshots(self):
        self.write(".env", "uncommitted")
        self.write("safe.txt", "worktree")
        for name in ("secret-scan", "sensitive-files"):
            self.rule(name, "release-readiness", 2)
            self.rule(name, "release-readiness", 2, PLEASE_PARAM_SNAPSHOT="invalid")
            self.rule(name, "check", 2, PLEASE_PARAM_SNAPSHOT="head")
            self.rule(name, "pre-push", 2, PLEASE_PARAM_SNAPSHOT="worktree")
            self.rule(name, "release-readiness", PLEASE_PARAM_SNAPSHOT="head")
        self.assertEqual(self.snapshot()["safe.txt"], "safe contents\n")
        self.rule(point="release-readiness", PLEASE_PARAM_SNAPSHOT="worktree")
        self.assertEqual(self.snapshot()["safe.txt"], "worktree")
        self.rule("sensitive-files", "release-readiness", 1, PLEASE_PARAM_SNAPSHOT="worktree")

    def test_missing_context_git_and_python_are_errors(self):
        for name in ("sensitive-files", "secret-scan"):
            self.rule(name, "unsupported", 2)
            directory = ROOT / "rules/checks" / name
            self.run_command(["sh", str(directory / "index.sh")], 2)
            env = dict(self.env, PATH=str(self.bin), PLEASE_RULE_DIRECTORY=str(directory), PLEASE_EXECUTION_POINT="check")
            self.run_command(["/bin/sh", str(directory / "index.sh")], 2, env)
            (self.bin / "python3").symlink_to(sys.executable)
            self.run_command(["/bin/sh", str(directory / "index.sh")], 2, env)
            (self.bin / "python3").unlink()
        self.git("update-ref", "-d", "HEAD")
        for name in ("sensitive-files", "secret-scan"):
            self.rule(name, "pre-push", 2)

    @unittest.skipUnless(GITLEAKS, "real Gitleaks not on PATH")
    def test_real_gitleaks_current_state_and_configuration(self):
        (self.bin / "gitleaks").unlink()
        (self.bin / "gitleaks").symlink_to(Path(GITLEAKS).resolve())
        self.rule()
        self.write("leak.txt", TOKEN)
        self.rule(expected=1)
        self.rule(point="pre-push")
        self.commit()
        (self.repo / "leak.txt").unlink()
        self.rule()
        self.rule(point="pre-push", expected=1)
        self.git("add", "-u")
        self.git("commit", "--quiet", "-m", "test: remove secret")
        self.rule(point="pre-push")
        # An allowed template filename is still scanned for actual secrets.
        self.write(".env.example", TOKEN)
        self.rule("sensitive-files")
        self.rule(expected=1)
        (self.repo / ".env.example").unlink()
        # Invalid uncommitted config affects check, but cannot change HEAD scanning.
        self.write(".gitleaks.toml", "invalid = [")
        self.rule(expected=2)
        self.rule(point="pre-push")
        (self.repo / ".gitleaks.toml").unlink()
        self.rule(GITLEAKS_CONFIG="/missing/config", GITLEAKS_CONFIG_TOML="invalid = [")

    @unittest.skipUnless(PLEASE, "published Please Behave not on PATH")
    def test_please_import_reports_and_real_pre_push_hook(self):
        source = self.base / "source"
        source.mkdir()
        shutil.copytree(ROOT / "rules", source / "rules")
        shutil.copytree(ROOT / "rulesets", source / "rulesets")
        shutil.copytree(ROOT / "scripts", source / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "feat: add security"], check=True)
        self.write(".please/config.toml", f'project = "My_App"\n[[imports]]\ngit = {json.dumps(str(source))}\npath = "rulesets/multi-point/security"\nref = "main"\n')
        (self.bin / "please").symlink_to(Path(PLEASE).resolve())
        self.run_command([PLEASE, "sync", "--yes"])
        source.rename(self.base / "offline-source")
        for point in ("check", "pre-push"):
            result = self.run_command([PLEASE, "run", "--at", point, "--plan", "--json"])
            plan = json.loads(result.stdout)
            self.assertEqual({r["origin"]["external"]["path"] for r in plan["scheduled"]}, {"rulesets/multi-point/security"})
            self.assertEqual(len(plan["scheduled"]), 2)
            self.run_command([PLEASE, "run", "--at", point])
        self.write(".env", "blocked")
        self.run_command([PLEASE, "run", "--at", "check"], 1)
        report = json.loads((self.repo / ".please/reports/last.json").read_text())
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(len(report["results"]), 2)
        self.rule("sensitive-files", "pre-push")
        remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--quiet", "--bare", str(remote)], check=True)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "--quiet", "origin", "main")  # Uncommitted violation is not in HEAD.
        self.commit()
        self.run_command(["git", "push", "--quiet", "origin", "main"], 1)
        self.fake(1, "[]")
        self.run_command([PLEASE, "run", "--at", "check"], 2)
        report = json.loads((self.repo / ".please/reports/last.json").read_text())
        self.assertEqual(report["overall"], "ERROR")
        self.assertEqual({item["status"] for item in report["results"]}, {"FAIL", "ERROR"})


if __name__ == "__main__":
    unittest.main()
