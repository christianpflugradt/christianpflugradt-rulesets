# Open-source software

The `rulesets/open-source-software` set includes the blocking `license`,
`workflow-syntax`, `ci-workflow`, `mise-prepare` and `shell-scripts` checks at `check` and `pre-push` and the `npm-audit` check at `check`.
The [quality assurance checks](#quality-assurance) follow the license section.
The `license` check It compares the target file byte-for-byte with the regular,
nonhidden files in `rules/checks/license/licenses/`. The included references are
Apache-2.0, PolyForm-Noncommercial-1.0.0 and Unlicense, downloaded unchanged
from [SPDX license-list-data](https://github.com/spdx/license-list-data/tree/31846481de7ea17d92f2f46fad76abe58b2e9bb0/text)
at commit `31846481de7ea17d92f2f46fad76abe58b2e9bb0`. Add or remove reference files to
change the allowlist. Whitespace, line endings and copyright notices must match.

Requirements: Python 3.9+ and Git. The Rule's own script compares the target with the
references in its `licenses` directory.

```toml
[[imports]]
git = "https://github.com/christianpflugradt/please-behave-governance.git"
path = "rulesets/open-source-software"
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

- `workflow-syntax` runs `actionlint` on the repository's GitHub workflows. It needs `actionlint` on
  `PATH` and a `.github/workflows` directory; issues return FAIL, and a missing tool ERROR.
- `shell-scripts` runs ShellCheck on every tracked `*.sh` file of the working tree, in any directory.
  Scripts whose shebang names zsh are skipped because ShellCheck cannot analyze them.
  Write portable POSIX `sh` (`#!/bin/sh`) where practical: ShellCheck then reports bashisms. Bash- or
  zsh-specific syntax is accepted but discouraged; the rule does not require `sh`.
  No scripts means PASS. Findings return FAIL; a missing tool or any other ShellCheck failure
  returns ERROR.
- `npm-audit` runs `npm audit --audit-level=high` for the directory of each tracked
  `package-lock.json` and fails on high or critical advisories. No lockfile means PASS. It runs
  only at `check` because it needs network access; registry or parsing problems return ERROR.

- `mise-prepare` requires a `prepare` task in the root `mise.toml` (same rules as the
  [Mise baseline](repository-conventions.md#mise-baseline); it needs Python 3.11+). The task
  fetches the locked dependencies that offline Git hooks and CI need, such as `npm ci`, so that
  `mise install` followed by `mise prepare` sets up a checkout. It is not specific to CI.

- `ci-workflow` requires `.github/workflows/ci.yml` to follow the shared structure:
  - `name: CI`, triggered by `push` to `main` and by `pull_request`; further triggers are allowed.
  - Top-level `permissions` are exactly `contents: read`.
  - A job with the id `check` that sets `timeout-minutes` and contains, in this order, with other
    steps allowed in between: `actions/checkout` with `persist-credentials: false`,
    `jdx/mise-action` without `install_args`, `run: mise run prepare`, and `please-behave/action`
    with `execution-point: check`, `install: 'false'` and `sync: 'true'`.
  - Every job sets `timeout-minutes`, and every `uses` of a remote action or workflow is pinned to a full commit SHA.

  Runners, matrices, timeout values, extra jobs and steps, secrets and artifact names are the
  repository's own. The rule checks structure only; it does not verify that CI ran or passed.
  It needs `yq` (v4) on `PATH` and Python 3.9+, and a missing tool or invalid YAML returns ERROR.

Requirements: Git, and Python 3.9+ for `shell-scripts`, `npm-audit` and `ci-workflow`, plus the tools named above.

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook. Exact matching enforces the
chosen reference texts; it does not identify licenses or assess their legal
suitability.
