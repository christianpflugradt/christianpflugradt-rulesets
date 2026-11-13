"""Semantic Release baseline: configuration shape, package pins, snapshots and technical failures."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context import write_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "rules/checks/semantic-release/check.py"
spec = importlib.util.spec_from_file_location("semantic_release_rule", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TAG = "v${version}"
PLUGIN = "./.github/scripts/semantic-release-plugin.mjs"


def baseline():
    return {
        "branches": ["main"], "tagFormat": TAG,
        "plugins": [
            [mod.ANALYZER, {"preset": "conventionalcommits", "parserOpts": copy.deepcopy(mod.PARSER_OPTS),
                            "releaseRules": copy.deepcopy(mod.RELEASE_RULES)}],
            [mod.NOTES, {"preset": "conventionalcommits", "parserOpts": copy.deepcopy(mod.PARSER_OPTS),
                         "presetConfig": {"types": copy.deepcopy(mod.NOTE_TYPES)}}],
            PLUGIN,
            [mod.GITHUB, {"successComment": False, "failComment": False, "releasedLabels": False}],
        ],
    }


def package():
    return {"private": True, "engines": {"node": ">=24.10.0 <27"},
            "devDependencies": {name: "1.2.3" for name in mod.DEPENDENCIES}}


def lock(manifest=None):
    return {"lockfileVersion": 3, "packages": {"": {"devDependencies": (manifest or package())["devDependencies"]}}}


def config_text():
    rules = json.dumps(mod.RELEASE_RULES)
    types = json.dumps(mod.NOTE_TYPES)
    return f"""const parserOpts = {{
  revertPattern: /^revert(?:\\([^)]+\\))?!?:\\s"?([\\s\\S]+?)"?\\s*This reverts commit (\\w*)\\./i,
  revertCorrespondence: ["header", "hash"],
}};
export default {{
  branches: ["main"],
  tagFormat: "v${{version}}",
  plugins: [
    ["@semantic-release/commit-analyzer", {{ preset: "conventionalcommits", parserOpts, releaseRules: {rules} }}],
    ["@semantic-release/release-notes-generator", {{ preset: "conventionalcommits", parserOpts,
      presetConfig: {{ types: {types} }} }}],
    "{PLUGIN}",
    ["@semantic-release/github", {{ successComment: false, failComment: false, releasedLabels: false }}],
  ],
}};
"""


def violations(config, tag=TAG, present=(PLUGIN[2:],)):
    return mod.config_violations(config, tag, lambda name: name in present)


class ConfigTests(unittest.TestCase):
    def test_baseline_and_repository_specific_parts_pass(self):
        self.assertEqual(violations(baseline()), [])
        config = baseline()
        config["repositoryUrl"] = "https://github.com/please-behave/cli.git"
        config["plugins"][3][1].update(assets=["dist/*.zip"], addReleases=False)
        self.assertEqual(violations(config), [])
        wrapper = baseline()
        wrapper["plugins"][0][0] = "./scripts/release-analyzer.mjs"
        wrapper["plugins"][0][1]["developmentSeries"] = True
        self.assertEqual(violations(wrapper, present=(PLUGIN[2:], "scripts/release-analyzer.mjs")), [])

    def test_rule_order_does_not_matter(self):
        config = baseline()
        config["plugins"][0][1]["releaseRules"].reverse()
        config["plugins"][1][1]["presetConfig"]["types"].reverse()
        self.assertEqual(violations(config), [])

    def test_legacy_tag_format_is_a_parameter(self):
        config = baseline()
        config["tagFormat"] = "${version}"
        self.assertEqual(len(violations(config)), 1)
        self.assertEqual(violations(config, tag="${version}"), [])

    def test_every_commit_type_is_mapped_once(self):
        types = (ROOT / "rules/checks/commit-message/commit-types.txt").read_text().split()
        for kind in types:
            with self.subTest(kind=kind):
                self.assertTrue([rule for rule in mod.RELEASE_RULES if rule.get("type") == kind])
                self.assertTrue([item for item in mod.NOTE_TYPES if item["type"] == kind])
        self.assertEqual(len(mod.canonical(mod.RELEASE_RULES)), len(set(mod.canonical(mod.RELEASE_RULES))))

    def test_deviations_are_reported(self):
        def edit(change):
            config = baseline()
            change(config)
            return config
        cases = {
            "extra option": edit(lambda c: c.update(dryRun=True)),
            "branches": edit(lambda c: c.update(branches=["main", "next"])),
            "repository url": edit(lambda c: c.update(repositoryUrl="https://example.org/x.git")),
            "added type": edit(lambda c: c["plugins"][0][1]["releaseRules"].append({"type": "major", "release": "major"})),
            "changed level": edit(lambda c: c["plugins"][0][1]["releaseRules"].__setitem__(
                5, {"type": "chore", "release": False})),
            "removed type": edit(lambda c: c["plugins"][1][1]["presetConfig"]["types"].pop()),
            "renamed section": edit(lambda c: c["plugins"][1][1]["presetConfig"]["types"][3].update(section="Deps")),
            "parser": edit(lambda c: c["plugins"][0][1]["parserOpts"].update(revertPattern="/x/")),
            "preset": edit(lambda c: c["plugins"][1][1].update(preset="angular")),
            "extra plugin": edit(lambda c: c["plugins"].insert(3, "@semantic-release/git")),
            "no verification plugin": edit(lambda c: c["plugins"].pop(2)),
            "unknown verification plugin": edit(lambda c: c["plugins"].__setitem__(2, "./missing.mjs")),
            "github comments": edit(lambda c: c["plugins"][3][1].update(successComment=True)),
            "github options missing": edit(lambda c: c["plugins"].__setitem__(3, mod.GITHUB)),
            "plain analyzer options": edit(lambda c: c["plugins"][0][1].update(extra=1)),
            "wrong analyzer": edit(lambda c: c["plugins"][0].__setitem__(0, "other")),
        }
        for label, config in cases.items():
            with self.subTest(label):
                self.assertTrue(violations(config), label)

    def test_not_an_object(self):
        self.assertEqual(len(violations([])), 1)


class PackageTests(unittest.TestCase):
    def test_baseline_passes_with_extras(self):
        manifest = package()
        manifest["devDependencies"]["js-yaml"] = "5.5.0"
        manifest["scripts"] = {"release": "node x.mjs"}
        self.assertEqual(mod.package_violations(manifest, lock(manifest)), [])

    def test_deviations_are_reported(self):
        def edit(change):
            manifest = package()
            change(manifest)
            return manifest
        cases = {
            "public": edit(lambda m: m.update(private=False)),
            "release key": edit(lambda m: m.update(release={})),
            "engines": edit(lambda m: m.pop("engines")),
            "range": edit(lambda m: m["devDependencies"].update({"semantic-release": "^25.0.0"})),
            "missing": edit(lambda m: m["devDependencies"].pop("semantic-release")),
        }
        for label, manifest in cases.items():
            with self.subTest(label):
                self.assertTrue(mod.package_violations(manifest, lock()), label)
        stale = lock()
        stale["packages"][""]["devDependencies"]["semantic-release"] = "9.9.9"
        self.assertEqual(len(mod.package_violations(package(), stale)), 1)
        self.assertEqual(len(mod.package_violations(package(), {})), 1)


@unittest.skipUnless(shutil.which("node"), "Node.js required")
class CommandTests(unittest.TestCase):
    def run_check(self, point, files, tag=TAG, commit=True, worktree=None):
        with tempfile.TemporaryDirectory(prefix="semantic-release-") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            for args in (["init", "--quiet"], ["config", "user.name", "T"], ["config", "user.email", "t@example.invalid"],
                         ["config", "commit.gpgsign", "false"]):
                subprocess.run(["git", *args], cwd=repo, check=True)
            for name, content in files.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(content)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "--quiet", "--allow-empty", "-m", "test: record"], cwd=repo, check=True)
            for name, content in (worktree or {}).items():
                (repo / name).write_text(content)
            context = write_context(temporary, point)
            return subprocess.run([sys.executable, "-B", str(SCRIPT), context, tag], cwd=repo,
                                  capture_output=True, text=True)

    def files(self, **changes):
        files = {"release.config.mjs": config_text(), "package.json": json.dumps(package()),
                 "package-lock.json": json.dumps(lock()), PLUGIN[2:]: "export function verifyRelease() {}\n"}
        files.update(changes)
        return {name: content for name, content in files.items() if content is not None}

    def test_baseline_passes_at_both_points(self):
        for point in ("check", "pre-push"):
            with self.subTest(point):
                result = self.run_check(point, self.files())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS", result.stdout)

    def test_missing_and_duplicate_configuration_fail(self):
        missing = self.run_check("check", self.files(**{"release.config.mjs": None}))
        self.assertEqual(missing.returncode, 1)
        self.assertIn("release.config.mjs is missing", missing.stdout)
        duplicate = self.run_check("check", self.files(**{".releaserc.json": "{}"}))
        self.assertEqual(duplicate.returncode, 1)
        self.assertIn(".releaserc.json duplicates", duplicate.stdout)
        no_lock = self.run_check("check", self.files(**{"package-lock.json": None}))
        self.assertEqual(no_lock.returncode, 1)

    def test_configuration_that_cannot_be_evaluated_fails(self):
        for text in ("export default {", 'import x from "./other.mjs";\nexport default {};\n'):
            with self.subTest(text=text):
                result = self.run_check("check", self.files(**{"release.config.mjs": text}))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("cannot be evaluated", result.stdout)

    def test_pre_push_reads_head_not_the_worktree(self):
        broken = {"release.config.mjs": config_text().replace('"main"', '"dev"')}
        self.assertEqual(self.run_check("pre-push", self.files(), worktree=broken).returncode, 0)
        self.assertEqual(self.run_check("check", self.files(), worktree=broken).returncode, 1)

    def test_deviation_names_the_problem(self):
        result = self.run_check("check", self.files(**{"release.config.mjs": config_text().replace('"main"', '"dev"')}))
        self.assertEqual(result.returncode, 1)
        self.assertIn('branches must be ["main"]', result.stdout)

    def test_legacy_tag_format_parameter(self):
        text = config_text().replace("v${version}", "${version}")
        self.assertEqual(self.run_check("check", self.files(**{"release.config.mjs": text}), tag="${version}").returncode, 0)
        self.assertEqual(self.run_check("check", self.files(**{"release.config.mjs": text})).returncode, 1)

    def test_technical_failures_are_errors(self):
        self.assertEqual(self.run_check("check", self.files(), tag="version").returncode, 2)
        self.assertEqual(self.run_check("commit-msg", self.files()).returncode, 2)
        self.assertEqual(self.run_check("check", self.files(**{"package.json": "{"})).returncode, 2)


if __name__ == "__main__":
    unittest.main()
