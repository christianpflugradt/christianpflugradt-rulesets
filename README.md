# Please Behave rule sets

Reusable checks and reviews for [Please Behave](https://github.com/please-behave/cli).
Requires published Please Behave v0.1.0 or later for string commands with explicit
path references. Commands run in the consuming repository root: `@rule/` selects
the declaring Rule directory and `@source/` selects this Git repository's root,
including when imported through Please Behave' immutable cache. No shell evaluation is
added; the three existing shell scripts still run through `sh`, and the shared
license script still runs through `python3`.

## Compatibility and migration

This revision uses the Please Behave `PLEASE_*` runtime environment and `.please/`
configuration. Existing Hannes consumers must retain the last compatible full
commit pin `86c1a09519de6e848e6f8a0110427ca8d136dd1c`. Historical pins remain usable.
Install Please Behave v0.1.0 before updating imports to this revision, migrate the
consumer configuration and run `please sync` to refresh the cache and hooks.
Rules, parameters, execution points, timeouts and enforcement remain unchanged.

## Conventional commit headers

The `commit-msg/conventional-commits` set validates commit headers at the
`commit-msg` execution point. It accepts `<type>[optional scope][!]: <description>`
with a nonblank description. Types come from
`rules/checks/commit-message/commit-types.txt`; scopes, when present, must match
an entry in the consuming project's scope file. Each file contains one exact,
case-sensitive value per line. The type list includes `config`.
Body and footer contents are not inspected.

The check needs POSIX `sh`, `dirname` and `grep`. Please Behave supplies the commit-message
file through `PLEASE_GIT_HOOK_ARG_1`, together with the `commit-msg` hook context.
Missing context, files or required parameters produce ERROR (exit 2); invalid
headers produce FAIL (exit 1); accepted headers produce PASS (exit 0).

Add this import to the consuming project's `.please/config.toml`:

```toml
[[imports]]
git = "https://github.com/christianpflugradt/christianpflugradt-rulesets.git"
path = "commit-msg/conventional-commits"
ref = "main"

[imports.rule_parameters.commit-message]
scopes_file = ".commit-scopes"
```

Create `.commit-scopes` at the consuming repository root, for example:

```text
cli
config
docs
```

Run `please sync` and confirm the import and managed hook installation.
The hook validates each subsequent commit message. Use a full commit hash instead
of `main` to pin the imported content. A direct `please run --at commit-msg`
invocation has no Git message argument and this check reports ERROR.

Rules live independently under `rules/checks/` and `rules/reviews/`. Sets refer
to their directories relative to this repository root; several sets may reuse
the same Rule. Resources stay together with the Rule's `rule.toml`.

## Security

The `multi-point/security` set runs two blocking checks at `check` and `pre-push`:

- `sensitive-files` rejects `.env` and `.env.*` filenames, except `.env.example`,
  `.env.sample` and `.env.template`, and files ending in `.tfstate` or containing
  `.tfstate.`. Matching is case-sensitive and applies in every directory.
- `secret-scan` scans file contents with Gitleaks.

`check` examines tracked and nonignored untracked working-tree files, including
unstaged edits. Deleted files are excluded; ignored files are included only when
tracked. `pre-push` examines the current `HEAD` tree, independent of working-tree
or index changes. Neither point scans Git history. `pre-push` does not inspect
other refs being pushed or consume Git's pre-push input.

Requirements: POSIX `sh`, Python 3.9+, Git and Gitleaks v8 supporting `gitleaks dir`
(tested with 8.30.1). Install these tools explicitly before running checks.
Please Behave and these rules install no dependencies.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/christianpflugradt-rulesets.git"
path = "multi-point/security"
ref = "main"
```

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook, then run
`please run --at check` to inspect the working tree explicitly.
See [scanner configuration and limitations](README-gitleaks.md).

## Repository conventions

The `repository-conventions` set currently includes only the blocking `license`
check. The existing `multi-point/license` set remains available and reuses the
same Rule. Both sets run it at `check` and `pre-push`. It compares the target file byte-for-byte with the regular,
nonhidden files in `rules/checks/license/licenses/`. The included references are
Apache-2.0, PolyForm-Noncommercial-1.0.0 and Unlicense, downloaded unchanged
from [SPDX license-list-data](https://github.com/spdx/license-list-data/tree/31846481de7ea17d92f2f46fad76abe58b2e9bb0/text)
at commit `31846481de7ea17d92f2f46fad76abe58b2e9bb0`. Add or remove reference files to
change the allowlist. Whitespace, line endings and copyright notices must match.

Requirements: Python 3.9+ and Git. The command
`python3 @source/scripts/file-reference.py` runs the shared script from this
repository root, while `PLEASE_RULE_DIRECTORY` still locates the Rule's license
references.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/christianpflugradt-rulesets.git"
path = "repository-conventions"
ref = "main"

[imports.rule_parameters.license]
target = "LICENSE"
```

`target` is a required string containing a repository-relative path without
parent traversal. `check` reads the working-tree file; `pre-push` reads that path
from the current `HEAD`, independently of working-tree changes. Neither point
scans history or every pushed commit. A match returns PASS (0); a missing or
nonmatching target returns FAIL (1); configuration or execution errors return
ERROR (2).

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook. Exact matching enforces the
chosen reference texts; it does not identify licenses or assess their legal
suitability.

## Validation

Run the script tests with Python 3:

```sh
python3 tests/test_commit_message.py
python3 -m unittest discover -s tests -v
```

To also test imports and real managed Git hooks in temporary repositories, supply
an absolute path to a compatible Please Behave binary:

```sh
python3 tests/test_commit_message.py --please /path/to/please
```

The tests use local Git repositories and never call a review provider. Security
integration tests use `please` and `gitleaks` from PATH when available, otherwise
those cases are reported as skipped. `PLEASE_EXECUTABLE` and
`GITLEAKS_EXECUTABLE` can select absolute tool paths. Run with both tools to verify
real scanner behavior, external imports, reports and managed pre-push enforcement.
