# Open-source software

The `rulesets/multi-point/open-source-software` set includes the blocking `license`,
`workflows` and `shell` checks at `check` and `pre-push` and the `npm-audit` check at `check`.
The [quality assurance checks](#quality-assurance) follow the license section.
The `license` check It compares the target file byte-for-byte with the regular,
nonhidden files in `rules/checks/license/licenses/`. The included references are
Apache-2.0, PolyForm-Noncommercial-1.0.0 and Unlicense, downloaded unchanged
from [SPDX license-list-data](https://github.com/spdx/license-list-data/tree/31846481de7ea17d92f2f46fad76abe58b2e9bb0/text)
at commit `31846481de7ea17d92f2f46fad76abe58b2e9bb0`. Add or remove reference files to
change the allowlist. Whitespace, line endings and copyright notices must match.

Requirements: Python 3.9+ and Git. The command
`python3 @source/scripts/file-reference.py` runs the shared script from this
repository root, and `@rule/licenses` locates the Rule's license references.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/please-behave-governance.git"
path = "rulesets/multi-point/open-source-software"
ref = "<FULL_REVIEWED_COMMIT_SHA>"

[imports.rule_parameters.license]
target = "LICENSE"
```

`target` is a required string containing a repository-relative path without
parent traversal. `check` reads the working-tree file; `pre-push` reads that path
from the current `HEAD`, independently of working-tree changes. Neither point
scans history or every pushed commit. A match returns PASS (0); a missing or
nonmatching target returns FAIL (1); configuration or execution errors return
ERROR (2).

## Quality assurance

- `workflows` runs `actionlint` on the repository's GitHub workflows. It needs `actionlint` on
  `PATH` and a `.github/workflows` directory; issues return FAIL, and a missing tool ERROR.
- `shell` runs ShellCheck on every tracked `*.sh` file of the working tree, in any directory.
  Scripts whose shebang names zsh are skipped because ShellCheck cannot analyze them.
  Write portable POSIX `sh` (`#!/bin/sh`) where practical: ShellCheck then reports bashisms. Bash- or
  zsh-specific syntax is accepted but discouraged; the rule does not require `sh`.
  No scripts means PASS. Findings return FAIL; a missing tool or any other ShellCheck failure
  returns ERROR.
- `npm-audit` runs `npm audit --audit-level=high` for the directory of each tracked
  `package-lock.json` and fails on high or critical advisories. No lockfile means PASS. It runs
  only at `check` because it needs network access; registry or parsing problems return ERROR.

Requirements: Git, and Python 3.9+ for `shell` and `npm-audit`, plus the tools named above.

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook. Exact matching enforces the
chosen reference texts; it does not identify licenses or assess their legal
suitability.

An aligned `ci.yml` quality-assurance workflow belongs to this policy bundle.
Checking its presence and structure is future work; this revision enforces only
the license policy.
