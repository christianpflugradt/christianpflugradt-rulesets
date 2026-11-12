"""The shared workflows, shell and npm-audit rules, with stub tools on PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "rules/checks/shell/check.py"
AUDIT = ROOT / "rules/checks/npm-audit/check.py"


class SharedChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="shared-checks-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.bin = Path(self.temp.name) / "bin"
        self.repo.mkdir()
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "init", "--quiet"], cwd=self.repo, check=True)

    def tool(self, name, body):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + body)
        path.chmod(0o755)

    def track(self, name, content="x\n"):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        subprocess.run(["git", "add", name], cwd=self.repo, check=True)

    def run_check(self, script, expected):
        result = subprocess.run([sys.executable, str(script)], cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_shell_without_scripts_passes_and_lists_every_tracked_script(self):
        self.run_check(SHELL, 0)
        self.track("a.sh")
        self.track("nested/b.sh")
        self.track("notes.txt")
        self.tool("shellcheck", "import sys\nopen('seen','w').write(' '.join(sys.argv[2:]))\n")
        self.run_check(SHELL, 0)
        self.assertEqual((self.repo / "seen").read_text(), "a.sh nested/b.sh")

    def test_shell_maps_findings_to_fail_and_tool_problems_to_error(self):
        self.track("a.sh")
        self.tool("shellcheck", "raise SystemExit(1)\n")
        self.run_check(SHELL, 1)
        self.tool("shellcheck", "raise SystemExit(2)\n")
        self.run_check(SHELL, 2)
        (self.bin / "shellcheck").unlink()
        self.env["PATH"] = f"{self.bin}:/usr/bin:/bin"  # Git only; no shellcheck.
        self.run_check(SHELL, 2)

    def npm(self, report, status=0):
        self.tool("npm", f"import sys\nprint({json.dumps(json.dumps(report))})\nraise SystemExit({status})\n")

    def test_npm_audit_without_lockfile_passes(self):
        self.run_check(AUDIT, 0)

    def test_npm_audit_audits_every_lockfile_and_fails_on_high_or_critical(self):
        self.track("package-lock.json", "{}")
        self.track("renderer/package-lock.json", "{}")
        self.npm({"metadata": {"vulnerabilities": {"low": 3, "high": 0, "critical": 0}}})
        self.run_check(AUDIT, 0)
        self.npm({"metadata": {"vulnerabilities": {"high": 1, "critical": 1}}}, 1)
        result = self.run_check(AUDIT, 1)
        self.assertIn("package-lock.json", result.stdout)
        self.assertIn("renderer/package-lock.json", result.stdout)

    def test_npm_audit_technical_failures_are_errors(self):
        self.track("package-lock.json", "{}")
        self.npm({"error": {"code": "ENOTFOUND"}}, 1)
        self.run_check(AUDIT, 2)
        self.tool("npm", "print('not json')\nraise SystemExit(1)\n")
        self.run_check(AUDIT, 2)
        (self.bin / "npm").unlink()
        self.env["PATH"] = f"{self.bin}:/usr/bin:/bin"  # Git only; no npm.
        self.run_check(AUDIT, 2)


if __name__ == "__main__":
    unittest.main()
