"""Technical failures exit 2 (ERROR); only a verdict about the checked subject exits 1 (FAIL)."""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = sorted(ROOT.glob("rules/checks/*/check.py")) + [ROOT / "scripts/file-reference.py"]
SNAPSHOT_USERS = [ROOT / "rules/checks/agents-size/check.py", ROOT / "rules/checks/editorconfig/check.py",
                  ROOT / "rules/checks/sensitive-files/check.py",
                  ROOT / "rules/checks/secret-scan/check.py", ROOT / "rules/checks/release-contract/check.py",
                  ROOT / "rules/checks/semantic-release/check.py",
                  ROOT / "scripts/file-reference.py"]


def guard_catches_exception(path):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.dump(node.test):
            for child in ast.walk(node):
                if isinstance(child, ast.ExceptHandler) and isinstance(child.type, ast.Name) \
                        and child.type.id == "Exception":
                    return True
    return False


class ExitContractTests(unittest.TestCase):
    def test_every_entry_script_maps_unexpected_exceptions_to_error(self):
        for path in CHECKS:
            with self.subTest(script=path.relative_to(ROOT).as_posix()):
                self.assertTrue(guard_catches_exception(path), "missing catch-all exit 2 guard")

    def test_missing_shared_helper_is_error_not_fail(self):
        for path in SNAPSHOT_USERS:
            with self.subTest(script=path.relative_to(ROOT).as_posix()):
                with tempfile.TemporaryDirectory(prefix="exit-contract-") as temporary:
                    copy = Path(temporary) / path.relative_to(ROOT)
                    copy.parent.mkdir(parents=True)
                    shutil.copyfile(path, copy)
                    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                    arguments = ["context.json", "1500", "LICENSE", "x"]
                    result = subprocess.run([sys.executable, str(copy), *arguments], cwd=temporary, env=env,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
