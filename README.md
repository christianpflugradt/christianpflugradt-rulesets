# Please Behave governance

Personal governance policies maintained by Christian Pflugradt for
[Please Behave](https://github.com/please-behave/cli). Rulesets group requirements
for repositories with common attributes and execution points. Import the bundles
that apply to a repository; each bundle adds to the others.

| Ruleset path | Repository group | Execution points | Current rules |
| --- | --- | --- | --- |
| `rulesets/commit-msg/repository-conventions` | Every repository, public or private, software or otherwise | `commit-msg` | Conventional Commit syntax and advisory header wording |
| `rulesets/multi-point/open-source-software` | Open-source software | `check`, `pre-push` | Approved license |
| `rulesets/multi-point/releasable-open-source-software` | Releasable open-source software | `release-readiness`, `release-record`, `release-verify` | Exact-source CI proof, candidate evidence and publication guards |
| `rulesets/multi-point/security` | Repositories adopting the security policy | `check`, `pre-push` | Sensitive filenames and secret scanning |

Repository conventions need Git hooks, without requiring CI or a `check` point.
Security is a deliberate domain separation. License checking belongs to the
open-source bundle. Aligned `ci.yml` and `release.yml` structure checks belong to
the open-source and release bundles respectively, but are **not implemented yet**.
This restructuring adds no checks and does not migrate existing consumers.

## Layout

```text
rulesets/
  <execution-point>/<ruleset>/config.toml  # One-point policy bundles
  multi-point/<ruleset>/config.toml        # Bundles assigned to several points
rules/checks/<rule>/                       # rule.toml, implementation and resources
rules/reviews/<rule>/                      # rule.toml, prompt and resources
providers/<provider>/                      # provider.toml and adapter
scripts/                                  # Reusable helpers and integration scripts
tests/                                    # Offline code and import integration tests
docs/                                     # Policy usage and compatibility details
```

Sets reference Rule directories relative to this repository root. Multiple sets
may reuse a Rule; consumers import provider packages independently. Commands run
in the consumer root: `@rule/` selects the Rule directory, `@source/` this source
repository, and `@provider/` an independently imported provider directory.
Imported source resources must remain immutable.

## Configuration

Use published Please Behave v0.5.0+ for the complete catalog. Install dependencies
explicitly; rules and providers never install tools. Pin each ruleset and provider
import to a reviewed full Git commit, then run `please sync` to validate resources
and confirm managed hook installation. Synchronization does not execute checks or
call providers. Subsequent execution loads the immutable cached revision offline;
the Gemini and GitHub API operations themselves still require network access.

| Bundle | Required consumer configuration | Tools and credentials |
| --- | --- | --- |
| Repository conventions | `commit-message.scopes_file`; independent `gemini-flash-lite` provider import | POSIX `sh`, `dirname`, `grep`; Python 3.9+ and `GEMINI_API_KEY` for wording |
| Open-source software | `license.target`, usually `LICENSE` | Python 3.9+, Git |
| Releasable open-source software | Three declared custom points; `release-contract.ci_policy` and `.artifacts_policy` | Python 3.11+, Git, Node 24+ for the publication guard, GitHub Actions context and `GITHUB_TOKEN` |
| Security | No required parameters at its assigned points | POSIX `sh`, Python 3.9+, Git, Gitleaks v8 with `gitleaks dir` |

The wording Review is advisory; its FAIL and ERROR results remain visible without
blocking commits. Deterministic checks are blocking. Security and license checks
inspect the working tree at `check` and `HEAD` at `pre-push`, without Git history
or every pushed ref. Technical failures never establish PASS.

See complete import examples, parameters, evidence boundaries and limitations:

- [Repository conventions and Gemini](docs/repository-conventions.md)
- [Open-source software and license policy](docs/open-source-software.md)
- [Release policy and artifact evidence](docs/releases.md)
- [Security and scanner configuration](docs/security.md)
- [Compatibility and path migration](docs/migration.md)
- [Shared Renovate governor preset](docs/governor-updates.md)

## Validation

Tests use temporary local Git repositories and mocked HTTP. They must never call
live providers or GitHub APIs. Use a published Please Behave binary for import and
managed-hook integration, independently of any CLI candidate under development.

```sh
python3 tests/test_commit_message.py
python3 -m unittest discover -s tests -v
node --test tests/test_release_guard.mjs
python3 tests/test_commit_message.py --please /path/to/published/please
```

`PLEASE_EXECUTABLE` and `GITLEAKS_EXECUTABLE` select tool paths for the Python
integration tests. Optional integrations report skips when tools are missing;
skips do not demonstrate successful integration. The repository currently has no
configured validation hooks or CI workflow. See [AGENTS.md](AGENTS.md) for change
boundaries and agent guidance.
