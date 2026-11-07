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

## Validation

Run the script tests with Python 3:

```sh
python3 tests/test_commit_message.py
```

To also test imports and real managed Git hooks in temporary repositories, supply
an absolute path to a compatible Hannes binary:

```sh
python3 tests/test_commit_message.py --hannes /path/to/hannes
```

The tests use local Git repositories and never call a review provider.
