# Please Behave rule sets

Personal checks and reviews maintained by Christian Pflugradt for [Please Behave](https://github.com/please-behave/cli).

## Releasable projects

Import `release/releasable-project` separately from the repository baseline.
Declare `release-readiness`, `release-record` and `release-verify` as custom points.
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

The original `release/readiness` set remains available for pinned consumers.

The current commit-message setup requires published Please Behave v0.5.0 or
later for independent provider imports and commit-header reviews. Other sets
retain their v0.1.0 minimum for explicit path references. Commands run in the
consuming repository root: `@rule/` selects
the declaring Rule directory and `@source/` selects this Git repository's root,
including when imported through Please Behave's immutable cache. No shell evaluation is
added; the three existing shell scripts still run through `sh`, and the shared
license script still runs through `python3`.

## Compatibility and migration

This revision uses the Please Behave `PLEASE_*` runtime environment and `.please/`
configuration. Existing Hannes consumers must retain the last compatible full
commit pin `86c1a09519de6e848e6f8a0110427ca8d136dd1c`. Historical pins remain usable.
For a runtime-only migration without wording reviews, published Please Behave
v0.1.0+ and pin `4825ec7d61ea01bd40cef3a126f107ef924f1666` retain the former
syntax-only set. Migrate the consumer to `.please/` and run `please sync`.

The current commit-message set adds an advisory Gemini wording Review.
Before updating this import, install published Please Behave v0.5.0+ and
configure local credentials.
Security, license and release-readiness behavior is unchanged by this addition.

## Commit headers and wording

The `commit-msg/conventional-commits` set contains a deterministic syntax Check
and an advisory wording Review at `commit-msg`. The Check accepts
`<type>[optional scope][!]: <description>`
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
git = "https://github.com/christianpflugradt/please-behave-rulesets.git"
path = "commit-msg/conventional-commits"
ref = "main"

[imports.rule_parameters.commit-message]
scopes_file = ".commit-scopes"
```

Import the named provider independently; no provider configuration or adapter
copy is needed in the consumer:

```toml
[[provider_imports]]
id = "gemini-flash-lite"
git = "https://github.com/christianpflugradt/please-behave-rulesets.git"
path = "providers/gemini-flash-lite"
ref = "main"
```

Pin both imports to reviewed full revisions. They use the same repository here,
but a consumer can select a provider from a separate organization repository.
The [provider package](providers/gemini-flash-lite/provider.toml) references the
shared [adapter](adapters/gemini.py) with `@source/adapters/gemini.py`. `please sync`
validates the definitions and cached resources without running the adapter;
subsequent hook execution uses the immutable cache offline for distribution.
Gemini calls themselves still require network and credentials. No dependencies
are installed automatically, and provider ID collisions are errors.

Create `.commit-scopes` at the consuming repository root, for example:

```text
cli
config
docs
```

The named provider requires Python 3.9+ and `GEMINI_API_KEY` in the environment of
the Git process. Keep credentials outside version control. Run `please sync` and
confirm the import and managed hook installation. It does not call Gemini.
Use a reviewed full commit hash instead of `main` to pin imported content.

On each commit or amend, the deterministic Check runs first. Syntax violations
block without a model call. The Review then evaluates only the captured first
line: English imperative wording and a specific action/target. Scope may provide
context. No word-count threshold, issue number or exhaustive description is
required. Routine dependency updates and recognizable reverts remain valid.

| Header | Wording expectation |
| --- | --- |
| `fix(settings): preserve keyboard focus after navigation` | PASS |
| `chore(deps): update dependencies` | PASS |
| `fix: fix stuff` | FAIL |
| `chore: do stuff` | FAIL |
| `feat: add stuff` | FAIL |
| `fix: fixed keyboard focus` | FAIL |

These are prompt acceptance examples, not deterministic predictions of an LLM's
judgment. The [prompt](rules/reviews/commit-message-quality/prompt.md) is the shared
wording policy. The [Review](rules/reviews/commit-message-quality/rule.toml) pins
`gemini-3.5-flash-lite` through adapter parameters; provider-level model defaults
cannot override that pin. Google documents this stable model and structured-output
support in the [model reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

The [adapter](adapters/gemini.py) uses Python's standard library and bounded HTTPS
`generateContent` requests with the complete prepared prompt and supplied JSON
Schema (`responseJsonSchema`). It has a 20-second HTTP timeout, a 2048-token output
limit and no fallback model. Transient connection failures/timeouts and HTTP
429/500/502/503/504 retry up to three total attempts, waiting 1 then 3 seconds.
Authentication errors and invalid, blocked, truncated or malformed responses are
not retried. The provider deadline is 70 seconds for the whole process.
Redirects are rejected so the key is never forwarded to another endpoint. Non-successful HTTP
responses, blocked/truncated candidates, invalid/duplicate JSON and responses over 64 KiB produce ERROR.
No raw API error text, credentials or prompts are printed. Authentication,
network and availability failures remain visible as Review ERROR. The Review
is temporarily non-blocking: wording FAIL and provider ERROR do not prevent a
commit, while deterministic syntax failures still block. Initial live probing
found HTTP 503 and empty-finding PASS responses for a revert header. Short retries
and the v0.5.0 header schema address those technical cases. The integration is
verified offline with the published governor; model judgment quality is not
claimed to be established, so enforcement remains advisory.

Please Behave sends only the header as review evidence, without body, diff,
source files or HEAD. Findings use `source: "commit-header"`, `path: null`,
`line: 1`; the CLI validates IDs, evidence and header stability. It rejects file
citations and incomplete verdicts. No comparison with the actual change occurs.
These rules do not inspect commit ranges or PR titles. The Review runs only at
`commit-msg`, not in CI `check`, pre-push or release readiness.

A direct `please run --at commit-msg` or offline preview has no Git message
argument and cannot run this set. Use a real Git commit/amend after setup, then
`please status --details` for saved evidence. The captured header is stored in the
local report; status does not review a later candidate message.

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
git = "https://github.com/christianpflugradt/please-behave-rulesets.git"
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
git = "https://github.com/christianpflugradt/please-behave-rulesets.git"
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

## Release readiness

`release/readiness` selects `github-ci-success`, `sensitive-files`, `secret-scan`
and `license` at the consumer-declared `release-readiness` execution point.
It uses the existing Please Behave parameter and import support; no CLI extension
is required. Rust builds, application smoke tests and packaging stay in consumers.

```toml
[execution_points]
custom = ["release-readiness"]

[[imports]]
git = "https://github.com/christianpflugradt/please-behave-rulesets.git"
path = "release/readiness"
ref = "<FULL_REVIEWED_COMMIT_SHA>"

[imports.rule_parameters.github-ci-success]
policy = ".please/release-ci.json"

[imports.rule_parameters.sensitive-files]
snapshot = "head"

[imports.rule_parameters.secret-scan]
snapshot = "head"

[imports.rule_parameters.license]
snapshot = "head"
target = "LICENSE"
```

The security and license rules now accept optional `snapshot = "head"` or
`"worktree"`. Existing `check` and `pre-push` defaults are unchanged; a conflicting
explicit selection is ERROR. Custom points require an explicit snapshot.
`head` reads committed blobs, independent of index/worktree changes; neither
selection scans history. Technical failures never establish PASS.

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

The tests use local Git repositories, mock Gemini HTTP and never call a live
review provider. The explicit commit-message integration command requires the
published v0.5.0+ executable and exercises the real imported Check/Review, managed
hooks, syntax gating, header-only HTTP payload, advisory FAIL/ERROR, invalid
evidence and missing credentials. Syntax rejection preserves HEAD; advisory
review results remain visible without rejecting the commit. Unit tests cover schema
forwarding, model selection, timeouts, redirects and invalid API envelopes. Security
integration tests use `please` and `gitleaks` from PATH when available, otherwise
those cases are reported as skipped. `PLEASE_EXECUTABLE` and
`GITLEAKS_EXECUTABLE` can select absolute tool paths. Run with both tools to verify
real scanner behavior, external imports, reports and managed pre-push enforcement.
