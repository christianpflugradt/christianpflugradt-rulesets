"""Require the shared Semantic Release baseline; project-specific release mechanics stay with consumers."""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

# Imported rule resources must remain immutable.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

CONFIG = "release.config.mjs"
# Other places Semantic Release reads its configuration from; a second source makes the result ambiguous.
OTHER_CONFIGS = [f".releaserc{suffix}" for suffix in ("", ".json", ".yaml", ".yml", ".js", ".cjs", ".mjs", ".ts")] + \
                [f"release.config{suffix}" for suffix in (".js", ".cjs", ".ts")]
PARSER_OPTS = {"revertPattern": r'/^revert(?:\([^)]+\))?!?:\s"?([\s\S]+?)"?\s*This reverts commit (\w*)\./i',
               "revertCorrespondence": ["header", "hash"]}
ANALYZER = "@semantic-release/commit-analyzer"
NOTES = "@semantic-release/release-notes-generator"
GITHUB = "@semantic-release/github"
# Every Conventional Commit type has exactly one release level and one place in the release notes.
RELEASE_RULES = [
    {"breaking": True, "release": "major"},
    {"type": "feat", "release": "minor"},
    *({"type": kind, "release": "patch"} for kind in ("fix", "perf", "revert", "chore", "refactor", "config")),
    # Generated version commits must never trigger another release.
    {"type": "build", "scope": "!release", "release": "patch"},
    {"type": "build", "scope": None, "release": "patch"},
    {"type": "build", "scope": "release", "release": False},
    *({"type": kind, "release": False} for kind in ("ci", "docs", "style", "test")),
]
NOTE_TYPES = [
    {"type": "feat", "section": "Features"},
    {"type": "fix", "section": "Bug Fixes"},
    {"type": "perf", "section": "Performance Improvements"},
    {"type": "chore", "section": "Maintenance"},
    {"type": "build", "scope": "release", "hidden": True},
    {"type": "build", "section": "Build System"},
    {"type": "refactor", "section": "Code Refactoring"},
    {"type": "revert", "section": "Reverts"},
    {"type": "config", "section": "Configuration"},
    *({"type": kind, "hidden": True} for kind in ("ci", "docs", "style", "test")),
]
DEPENDENCIES = ("semantic-release", ANALYZER, NOTES, GITHUB, "conventional-changelog-conventionalcommits")
TOP_LEVEL = {"branches", "tagFormat", "repositoryUrl", "plugins"}
GITHUB_REQUIRED = {"successComment": False, "failComment": False, "releasedLabels": False}
REPOSITORY_URL = re.compile(r"https://github\.com/(?:please-behave|christianpflugradt)/[A-Za-z0-9_.-]+\.git")
EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")


def canonical(items):
    return sorted(json.dumps(item, sort_keys=True) for item in items)


def same_set(actual, expected):
    return isinstance(actual, list) and canonical(actual) == canonical(expected)


def plugin(entry):
    """Return (name, options) for a plugin declared as a name or as [name, options]."""
    if isinstance(entry, str):
        return entry, {}
    if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str) and isinstance(entry[1], dict):
        return entry[0], entry[1]
    return None, {}


def local(name):
    if not isinstance(name, str) or not name.startswith("./"):
        return False
    path = PurePosixPath(name[2:])
    return bool(path.parts) and ".." not in path.parts and path.suffix == ".mjs" and str(path) == name[2:]


def config_violations(config, tag_format, exists):
    """List deviations of a loaded config; `exists` tells whether a repository file is present."""
    if not isinstance(config, dict):
        return [f"{CONFIG} must export a configuration object"]
    found = [f"{CONFIG} option {key} is not part of the baseline" for key in sorted(set(config) - TOP_LEVEL)]
    if config.get("branches") != ["main"]:
        found.append('branches must be ["main"]')
    if config.get("tagFormat") != tag_format:
        found.append(f"tagFormat must be {tag_format}")
    if "repositoryUrl" in config and not (isinstance(config["repositoryUrl"], str)
                                          and REPOSITORY_URL.fullmatch(config["repositoryUrl"])):
        found.append("repositoryUrl must be a GitHub .git URL of the owning account")
    entries = config.get("plugins")
    if not isinstance(entries, list) or len(entries) < 3:
        return found + ["plugins must be: analyzer, release notes generator, optional local plugins, GitHub"]
    analyzer, notes, github = plugin(entries[0]), plugin(entries[1]), plugin(entries[-1])

    name, options = analyzer
    wrapper = local(name)
    if name != ANALYZER and not wrapper:
        found.append(f"the first plugin must be {ANALYZER} or a local wrapper (./path.mjs)")
    else:
        if wrapper and not exists(name[2:]):
            found.append(f"analyzer wrapper {name[2:]} is missing")
        required = {"preset", "parserOpts", "releaseRules"}
        if options.get("preset") != "conventionalcommits":
            found.append("analyzer preset must be conventionalcommits")
        if options.get("parserOpts") != PARSER_OPTS:
            found.append("analyzer parserOpts must be the shared revert parsing")
        if not same_set(options.get("releaseRules"), RELEASE_RULES):
            found.append("analyzer releaseRules must be exactly the shared release levels")
        if not wrapper and set(options) != required:
            found.append(f"analyzer options must be exactly {', '.join(sorted(required))}")

    name, options = notes
    if name != NOTES:
        found.append(f"the second plugin must be {NOTES}")
    else:
        if set(options) != {"preset", "parserOpts", "presetConfig"}:
            found.append("release notes options must be exactly preset, parserOpts and presetConfig")
        if options.get("preset") != "conventionalcommits":
            found.append("release notes preset must be conventionalcommits")
        if options.get("parserOpts") != PARSER_OPTS:
            found.append("release notes parserOpts must be the shared revert parsing")
        preset = options.get("presetConfig")
        if not (isinstance(preset, dict) and set(preset) == {"types"} and same_set(preset["types"], NOTE_TYPES)):
            found.append("release notes types must be exactly the shared sections")

    for entry in entries[2:-1]:
        name, options = plugin(entry)
        if not local(name) or options:
            found.append("plugins between the release notes generator and GitHub must be local, given as a plain ./path.mjs")
        elif not exists(name[2:]):
            found.append(f"local plugin {name[2:]} is missing")

    name, options = github
    if name != GITHUB:
        found.append(f"the last plugin must be {GITHUB}")
    else:
        for key, value in GITHUB_REQUIRED.items():
            if options.get(key) is not value:
                found.append(f"{GITHUB} option {key} must be false")
    return found


def package_violations(package, lock):
    found = []
    if package.get("private") is not True:
        found.append("package.json must set private to true")
    if "release" in package:
        found.append("package.json must not carry a release configuration")
    engines = package.get("engines")
    if not (isinstance(engines, dict) and isinstance(engines.get("node"), str) and engines["node"]):
        found.append("package.json must declare engines.node")
    scripts = package.get("devDependencies")
    scripts = scripts if isinstance(scripts, dict) else {}
    for name in DEPENDENCIES:
        version = scripts.get(name)
        if not (isinstance(version, str) and EXACT_VERSION.fullmatch(version)):
            found.append(f"devDependency {name} must be pinned to an exact version")
    root = (lock.get("packages") or {}).get("") if isinstance(lock, dict) else None
    locked = root.get("devDependencies") if isinstance(root, dict) else None
    if not isinstance(locked, dict) or any(locked.get(name) != scripts.get(name) for name in DEPENDENCIES):
        found.append("package-lock.json does not match the pinned devDependencies")
    return found


def load_json(content, name):
    try:
        return json.loads(content)
    except ValueError:
        raise ValueError(f"{name} is not valid JSON") from None


def evaluate(content):
    """Run the config module in an isolated directory so that it cannot reach repository files."""
    with tempfile.TemporaryDirectory(prefix="semantic-release-") as temporary:
        target = Path(temporary) / CONFIG
        target.write_bytes(content)
        result = subprocess.run(["node", str(Path(__file__).with_name("evaluate.mjs")), str(target)],
                                cwd=temporary, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode == 1:
        return None, result.stderr.strip().splitlines()[:1] or ["unknown error"]
    if result.returncode != 0:
        raise RuntimeError("node could not evaluate the configuration")
    return json.loads(result.stdout), []


def main():
    from snapshot import execution_point, read_file, select_snapshot
    if len(sys.argv) != 3:
        raise ValueError("expected arguments: context file and tag format")
    tag_format = sys.argv[2]
    if "${version}" not in tag_format:
        raise ValueError("tag_format must contain ${version}")
    point = execution_point(sys.argv[1])
    snapshot = select_snapshot(point)

    def exists(name):
        return read_file(snapshot, name) is not None

    found = []
    content = read_file(snapshot, CONFIG)
    if content is None:
        found.append(f"{CONFIG} is missing")
    else:
        found += [f"{name} duplicates the Semantic Release configuration" for name in OTHER_CONFIGS if exists(name)]
        config, errors = evaluate(content)
        found += [f"{CONFIG} cannot be evaluated: {error}" for error in errors]
        if config is not None:
            found += config_violations(config, tag_format, exists)
    package = read_file(snapshot, "package.json")
    lock = read_file(snapshot, "package-lock.json")
    if package is None or lock is None:
        found.append("package.json and package-lock.json are required")
    else:
        found += package_violations(load_json(package, "package.json"), load_json(lock, "package-lock.json"))
    for message in found:
        print(f"FAIL: {message}")
    if not found:
        print(f"PASS: Semantic Release baseline satisfied ({point})")
    return 1 if found else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
