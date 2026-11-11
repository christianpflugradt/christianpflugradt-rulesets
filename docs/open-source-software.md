# Open-source software

The `rulesets/multi-point/open-source-software` set currently includes the blocking
`license` check at `check` and `pre-push`. It compares the target file byte-for-byte with the regular,
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

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook. Exact matching enforces the
chosen reference texts; it does not identify licenses or assess their legal
suitability.

An aligned `ci.yml` quality-assurance workflow belongs to this policy bundle.
Checking its presence and structure is future work; this revision enforces only
the license policy.
