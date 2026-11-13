# Releasable open-source software

Import `rulesets/releasable-open-source-software` separately from the
repository baseline.
Declare `release-readiness`, `release-record` and `release-verify` as custom points.
For example, in the consumer's `.please/config.toml`:

```toml
[execution_points]
custom = ["release-readiness", "release-record", "release-verify"]

[[imports]]
git = "https://github.com/christianpflugradt/please-behave-governance.git"
path = "rulesets/releasable-open-source-software"
ref = "<FULL_REVIEWED_COMMIT_SHA>"

[imports.rule_parameters.release-contract]
ci_policy = ".please/release-ci.json"
artifacts_policy = ".please/release-artifacts.json"

[imports.rule_parameters.semantic-release]
tag_format = "v${version}"
```

## Semantic Release baseline

The blocking `semantic-release` Check runs at `check` and `pre-push` (`HEAD`). It
evaluates `release.config.mjs` with Node in an isolated directory, so the module must
be self-contained, and reads `package.json` and `package-lock.json`. It does not
inspect workflows or GitHub. Requirements:

- `release.config.mjs` is the only configuration source: no `.releaserc*`, no other
  `release.config.*` and no `release` key in `package.json`.
- Only `branches`, `tagFormat`, `repositoryUrl` and `plugins` are set. `branches` is
  `["main"]`. `tagFormat` equals the required `tag_format` parameter, normally
  `v${version}`; a repository with legacy tags declares `${version}`. `repositoryUrl`
  is optional.
- Exactly four plugins in order: commit analyzer, release notes generator, a local
  verification plugin (a plain `./path.mjs` that must exist) and
  `@semantic-release/github`. Changelog, Git and npm plugins are therefore excluded.
- Analyzer and notes generator use preset `conventionalcommits`, the shared revert
  `parserOpts` and exactly the shared release levels and sections:

| Commit type | Release | Notes section |
| --- | --- | --- |
| breaking | major | none of its own |
| `feat` | minor | Features |
| `fix`, `perf`, `revert` | patch | Bug Fixes, Performance Improvements, Reverts |
| `chore`, `refactor`, `build`, `config` | patch | Maintenance, Code Refactoring, Build System, Configuration |
| `build(release)` | none | hidden |
| `ci`, `docs`, `style`, `test` | none | hidden |

- The analyzer may be a local wrapper (`./path.mjs`, which must exist) around the
  commit analyzer; it keeps the same options and may add its own.
- `@semantic-release/github` sets `successComment`, `failComment` and `releasedLabels`
  to `false`; `assets` and further options are the repository's own.
- `package.json` sets `private: true` and `engines.node`, and pins `semantic-release`,
  the three `@semantic-release/*` plugins and `conventional-changelog-conventionalcommits`
  to exact versions that `package-lock.json` matches. Other fields and dependencies are
  the repository's own.

Local plugin contents, `assets`, versions and engine bounds are not standardized.

The `release-contract` Check has two required file parameters: `ci_policy` uses
the existing exact-source CI policy below; `artifacts_policy` uses this format:

```json
{
  "schema_version": 1,
  "repository": "please-behave/cli",
  "workflow": ".github/workflows/release.yml",
  "root": "dist",
  "targets": {"linux": ["app-{version}.tar.gz"]}
}
```

Readiness reuses the existing trusted CI proof, including partial CI reruns,
without repeating source checks or imposing an age limit. After successful
artifact-specific candidate tests, run `release-record` with `RELEASE_TARGET`.
It writes `release-evidence/TARGET.json` with schema version, repository, workflow,
source SHA, planned version, run ID/attempt, target and SHA-256 hashes for every
listed artifact. `{version}` is the only path substitution. Paths are relative
to `root`; use `.` for repository-content releases such as composite Actions.

Upload each evidence file separately from public assets. After collecting all
candidates and evidence, `release-verify` requires exactly the configured target
set and validates every identity and digest against the current release context.
Set `EXPECTED_RELEASE_VERSION` at both points. Only `release.yml` on main is
accepted. Missing, foreign, altered or earlier-attempt evidence blocks publication;
rerun the whole Release workflow after a partial candidate rerun. Symlinks,
traversal and duplicate JSON keys are rejected. Existing artifact-specific
validation remains responsible for archive contents, executable versions,
runtime receipts and any generated aggregate checksum file. The manifest is
internal workflow evidence, not a signature or an independent attestation.

Generated artifacts, `release-evidence/` and the GitHub environment file must stay
outside the consumer's governed source snapshot, for example through ignore
patterns. Candidate recording and verification write workflow evidence, while
Please Behave still checks that governed source files remain stable.

On successful `release-verify`, the Check exports `PLEASE_RELEASE_GUARD` and
`PLEASE_RELEASE_REPOSITORY` through GitHub's environment file. The first is the
immutable cached `scripts/release-guard.mjs` module, which thin local Semantic
Release adapters load with Node's `createRequire`. Its synchronous `verifyRelease`
hook compares Semantic Release's recalculated version with the plan, then checks
the actual checkout, dispatched SHA, expected repository, main branch and current
remote main immediately before tagging. `verifySource` provides the same source
guard for custom prerelease publication. No repository needs a copied source or
version-check implementation. Node 24+ and Python 3.11+ are required for these gates.

## Trusted CI policy

The CI policy file has this exact schema (no step configuration):

```json
{
  "schema_version": 1,
  "repository": "please-behave/cli",
  "workflow": ".github/workflows/ci.yml",
  "event": "push",
  "branch": "main",
  "required_jobs": ["Check"]
}
```

List every required matrix entry by its unique, exact GitHub job name. This
personal rule supports GitHub.com push workflows in the `please-behave` organization
and `christianpflugradt` account. It requires Python 3.9+, Git, `GITHUB_TOKEN`
with `actions: read` and `contents: read`, and the standard `GITHUB_SHA`,
`GITHUB_REPOSITORY`, `GITHUB_REPOSITORY_ID`, `GITHUB_RUN_ID` and
`GITHUB_WORKFLOW_REF` release context. The checkout must equal `GITHUB_SHA`.

The rule resolves repository/workflow IDs and checks source/head repository,
workflow path, exact SHA, branch and event. It chooses the newest matching run
without filtering for success. Missing, pending, failed or cancelled runs block;
an older green run cannot substitute. The selected run must be completed and
successful. For partial reruns, attempt-specific job lists are read newest first;
the newest execution of each required job wins. Successful jobs retained from an
earlier attempt of that same run count. A later failure/skip overrides an earlier
success. Unrelated runs never combine. Ambiguous job names, incomplete API pages,
changed evidence or identity mismatches are ERROR. The run is reread and newest-run
selection repeated before PASS. No individual steps are inspected.

GitHub's completed run and per-attempt job records are the evidence boundary:
this trusts the reviewed workflow/configuration at the source commit, rather than
proving its commands independently. Evidence is a point-in-time API observation,
not a signed attestation or an atomic lock against future reruns. The current
release run/workflow cannot certify itself; CI must not wait on release readiness.
The rule never dispatches CI or polls for its completion. Retry the release after
CI succeeds. API/authentication/network/JSON failures are ERROR, with raw diagnostics
suppressed. Authentication redirects and non-GitHub API hosts are rejected.
To keep evidence bounded, more than 100 attempts or 1000+ entries in an API listing are
unsupported and fail closed. Stable, unique job names
are required across attempts; dynamic names that hide a rerun's identity cannot
be validated reliably.

References: [workflow runs](https://docs.github.com/en/rest/actions/workflow-runs),
[attempt jobs](https://docs.github.com/en/rest/actions/workflow-jobs).

Checking the complete structure of `ci.yml` and `release.yml` is future work.
The existing contract checks CI evidence and release identity, artifacts and
publication context; it does not validate arbitrary workflow contents.
