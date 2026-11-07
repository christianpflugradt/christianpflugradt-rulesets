"""Filename policy boundaries."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "rules/checks/sensitive-files/check.py"
spec = importlib.util.spec_from_file_location("sensitive_files", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SensitiveFilesTests(unittest.TestCase):
    def test_blocked(self):
        for name in (".env", ".env.test", "nested/.env.production", "main.tfstate",
                     "main.tfstate.backup", "nested/a.tfstate.copy", ".env.example.local"):
            with self.subTest(name=name):
                self.assertTrue(mod.prohibited(name))

    def test_allowed(self):
        for name in (".env.example", "nested/.env.sample", ".env.template", ".environment.txt",
                     "main.tfvars", ".npmrc", "server.pem", "server.key", "main.tfstateful"):
            with self.subTest(name=name):
                self.assertFalse(mod.prohibited(name))


if __name__ == "__main__":
    unittest.main()
