"""Canonical bundles import and execute from an offline immutable cache."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLEASE = os.environ.get("PLEASE_EXECUTABLE") or shutil.which("please")


@unittest.skipUnless(PLEASE, "published Please Behave required")
class RulesetIntegrationTests(unittest.TestCase):
    def test_additive_bundles_and_cached_release_resources(self):
        with tempfile.TemporaryDirectory(prefix="ruleset-catalog-") as temporary:
            base = Path(temporary)
            source, consumer = base / "source", base / "consumer"
            source.mkdir()
            consumer.mkdir()
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PLEASE_", "GITHUB_"))}
            env.update(XDG_CACHE_HOME=str(base / "cache"), NO_COLOR="1",
                       GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       PYTHONDONTWRITEBYTECODE="1")

            def run(args, cwd=consumer, expected=0):
                result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result.stdout

            def git(cwd, *args):
                return run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "-c", "commit.gpgsign=false", *args], cwd=cwd)

            for directory in ("rulesets", "rules", "providers", "scripts"):
                shutil.copytree(ROOT / directory, source / directory,
                                ignore=shutil.ignore_patterns("__pycache__"))
            for repo in (source, consumer):
                git(repo, "init", "--quiet", "--initial-branch=main")
            git(source, "add", ".")
            git(source, "commit", "--quiet", "-m", "test: record canonical bundles")
            revision = git(source, "rev-parse", "HEAD").strip()
            paths = ["rulesets/multi-point/repository-conventions", "rulesets/multi-point/open-source-software",
                     "rulesets/multi-point/releasable-open-source-software", "rulesets/multi-point/security"]
            (consumer / ".please").mkdir()
            config = 'project = "Catalog fixture"\n[execution_points]\n'
            config += 'custom = ["release-readiness", "release-record", "release-verify"]\n'
            for path in paths:
                config += f'\n[[imports]]\ngit = {json.dumps(str(source))}\npath = "{path}"\nref = "{revision}"\n'
                if path.endswith("repository-conventions"):
                    config += '[imports.rule_parameters.commit-message]\nscopes_file = ".commit-scopes"\n'
                    config += '[imports.rule_parameters.agents-size]\nmax_tokens = "1500"\n'
                elif path.endswith("/open-source-software"):
                    config += '[imports.rule_parameters.license]\ntarget = "LICENSE"\n'
                elif path.endswith("releasable-open-source-software"):
                    config += '[imports.rule_parameters.release-contract]\nci_policy = "ci.json"\nartifacts_policy = "artifacts.json"\n'
            config += ('\n[[provider_imports]]\nid = "gemini-flash-lite"\n'
                       f'git = {json.dumps(str(source))}\npath = "providers/gemini-flash-lite"\nref = "{revision}"\n')
            (consumer / ".please/config.toml").write_text(config)
            (consumer / ".commit-scopes").write_text("docs\n")
            (consumer / ".gitignore").write_text(".please/reports/\ndist/\nrelease-evidence/\nenvironment\n")
            shutil.copyfile(ROOT / "rules/checks/license/licenses/Unlicense.txt", consumer / "LICENSE")
            (consumer / "ci.json").write_text("{}")
            (consumer / "artifacts.json").write_text(json.dumps({
                "schema_version": 1, "repository": "please-behave/cli",
                "workflow": ".github/workflows/release.yml", "root": "dist",
                "targets": {"linux": ["app-{version}"]},
            }))
            git(consumer, "add", ".")
            git(consumer, "commit", "--quiet", "-m", "test: record consumer")
            run([PLEASE, "sync", "--yes"])
            source.rename(base / "offline-source")
            expected = {
                "pre-commit": {"agents-size"},
                "commit-msg": {"commit-message", "commit-message-quality"},
                "check": {"agents-size", "license", "secret-scan", "sensitive-files"},
                "pre-push": {"license", "secret-scan", "sensitive-files"},
                "release-readiness": {"release-contract"},
                "release-record": {"release-contract"},
                "release-verify": {"release-contract"},
            }
            for point, rules in expected.items():
                with self.subTest(point=point):
                    plan = json.loads(run([PLEASE, "run", "--at", point, "--plan", "--json"],
                                          expected=2 if point == "commit-msg" else 0))
                    self.assertEqual({rule["id"].rsplit(":", 1)[-1] for rule in plan["scheduled"]}, rules)
                    for rule in plan["scheduled"]:
                        self.assertEqual(rule["origin"]["external"]["commit"], revision)
                    if point == "commit-msg":
                        self.assertEqual(plan["blocking_reasons"], [
                            "Cannot prepare review input: commit-header review requires the managed commit-msg hook"])
            env.update(GITHUB_SHA=git(consumer, "rev-parse", "HEAD").strip(),
                       GITHUB_REF="refs/heads/main", GITHUB_REPOSITORY="please-behave/cli",
                       GITHUB_WORKFLOW_REF="please-behave/cli/.github/workflows/release.yml@refs/heads/main",
                       GITHUB_RUN_ID="12", GITHUB_RUN_ATTEMPT="1", RELEASE_TARGET="linux",
                       EXPECTED_RELEASE_VERSION="1.2.3", GITHUB_ENV=str(consumer / "environment"))
            (consumer / "dist").mkdir()
            artifact = consumer / "dist/app-1.2.3"
            artifact.write_bytes(b"tested candidate")
            run([PLEASE, "run", "--at", "release-record"])
            run([PLEASE, "run", "--at", "release-verify"])
            exports = (consumer / "environment").read_text().splitlines()
            guard = Path(next(line.split("=", 1)[1] for line in exports if line.startswith("PLEASE_RELEASE_GUARD=")))
            self.assertTrue(guard.is_file())
            self.assertTrue(guard.as_posix().endswith("/scripts/release-guard.mjs"))
            artifact.write_bytes(b"altered candidate")
            run([PLEASE, "run", "--at", "release-verify"], expected=2)


if __name__ == "__main__":
    unittest.main()
