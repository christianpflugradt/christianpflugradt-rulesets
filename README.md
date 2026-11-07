# Hannes rule sets

Reusable checks and reviews for [Hannes](https://github.com/christianpflugradt/hannes).
Requires a Hannes release supporting repository-relative external Rule references.
Older releases with directory-local Rule references cannot load this layout.

## Conventional commit headers

The `commit-msg/conventional-commits` set validates commit headers at the
`commit-msg` execution point. It accepts `<type>[optional scope][!]: <description>`
with a nonblank description. Types come from
`rules/checks/commit-message/commit-types.txt`; scopes, when present, must match
an entry in the consuming project's scope file. Each file contains one exact,
case-sensitive value per line. The type list includes `config`.
Body and footer contents are not inspected.

The check needs POSIX `sh`, `dirname` and `grep`. Hannes supplies the commit-message
file through `HANNES_GIT_HOOK_ARG_1`, together with the `commit-msg` hook context.
Missing context, files or required parameters produce ERROR (exit 2); invalid
headers produce FAIL (exit 1); accepted headers produce PASS (exit 0).

Add this import to the consuming project's `.hannes/config.toml`:

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

Run `hannes pass auf` and confirm the import and managed hook installation.
The hook validates each subsequent commit message. Use a full commit hash instead
of `main` to pin the imported content. A direct `hannes mach was --at commit-msg`
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
Hannes and these rules install no dependencies.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/christianpflugradt-rulesets.git"
path = "multi-point/security"
ref = "main"
```

Pin a full commit hash for reproducible imports. Run `hannes pass auf` to resolve
the import and install the managed pre-push hook, then run
`hannes mach was --at check` to inspect the working tree explicitly.
See [scanner configuration and limitations](README-gitleaks.md).

## License

The `multi-point/license` set runs the blocking `license` check at `check` and
`pre-push`. It compares the target file byte-for-byte with the regular,
nonhidden files in `rules/checks/license/licenses/`. The included references are
Apache-2.0 and PolyForm-Noncommercial-1.0.0. Add or remove reference files to
change the allowlist. Whitespace, line endings and copyright notices must match.

Requirements: Python 3.9+ and Git. The check uses the shared entrypoint
`scripts/file-reference.py`; this requires Hannes support for source-relative
check entrypoints.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/christianpflugradt-rulesets.git"
path = "multi-point/license"
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

Pin a full commit hash for reproducible imports. Run `hannes pass auf` to resolve
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
an absolute path to a compatible Hannes binary:

```sh
python3 tests/test_commit_message.py --hannes /path/to/hannes
```

The tests use local Git repositories and never call a review provider. Security
integration tests use `hannes` and `gitleaks` from PATH when available, otherwise
those cases are reported as skipped. `HANNES_EXECUTABLE` and
`GITLEAKS_EXECUTABLE` can select absolute tool paths. Run with both tools to verify
real scanner behavior, external imports, reports and managed pre-push enforcement.
