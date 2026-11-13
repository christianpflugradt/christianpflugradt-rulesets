# Please Behave governance

Personal governance policies maintained by Christian Pflugradt for
[Please Behave](https://github.com/please-behave/cli). Rulesets group requirements
for repositories with common attributes and execution points. Import the bundles
that apply to a repository; each bundle adds to the others.

| Ruleset path | Repository group | Execution points | Current rules |
| --- | --- | --- | --- |
| `rulesets/repository-conventions` | Every repository, public or private, software or otherwise | `pre-commit`, `check`; `commit-msg` for commit rules | `AGENTS.md` size limit, EditorConfig baseline, Conventional Commit syntax and advisory header wording, mise governor pin with `format` and `verify` tasks |
| `rulesets/open-source-software` | Open-source software | `check`, `pre-push` | Approved license, `prepare` task, CI workflow structure |
| `rulesets/releasable-open-source-software` | Releasable open-source software | `check`, `pre-push` | Semantic Release baseline, `release` task, Release workflow structure |
| `rulesets/security` | Repositories adopting the security policy | `check`, `pre-push` | Sensitive filenames and secret scanning |

Repository conventions stay lightweight and work through Git hooks alone; `check` adds the same size limit and EditorConfig baseline to CI.
Security is a deliberate domain separation. License checking belongs to the
open-source bundle.

## Layout

```text
rulesets/
  <ruleset>/config.toml                    # Policy bundles, grouped logically rather than by execution point
rules/checks/<rule>/                       # rule.toml, implementation and resources
rules/reviews/<rule>/                      # rule.toml, prompt and resources
providers/<provider>/                      # provider.toml and adapter
docs/                                     # Policy usage and compatibility details
```

Sets reference Rule directories relative to this repository root. Multiple sets
may reuse a Rule; consumers import provider packages independently. Commands run
in the consumer root: `@rule/` selects the Rule directory, `@source/` this source
repository, and `@provider/` an independently imported provider directory.
Imported source resources must remain immutable.

## Configuration

Use published Please Behave 0.8.0 or later for the complete catalog. Install dependencies
explicitly; rules and providers never install tools. Pin each ruleset and provider
import to a reviewed full Git commit, then run `please sync` to validate resources
and confirm managed hook installation. Synchronization does not execute checks or
call providers. Subsequent execution loads the immutable cached revision offline;
the Gemini operations themselves still require network access.

| Bundle | Required consumer configuration | Tools and credentials |
| --- | --- | --- |
| Repository conventions | `agents-size.max_tokens`; `commit-message.scopes_file`; independent `gemini-flash-lite` and `gemini-flash` provider imports | Python 3.9+ (3.11+ for the mise tasks check), Git and `GEMINI_API_KEY` for the wording and `AGENTS.md` reviews |
| Open-source software | `license.target`, usually `LICENSE` | Python 3.9+ (3.11+ for the `prepare` task check), Git, `actionlint`, ShellCheck, `yq`, npm |
| Releasable open-source software | `semantic-release.tag_format` | Python 3.11+, Git, Node 24+, `yq` |
| Security | No required parameters at its assigned points | Python 3.9+, Git, Gitleaks v8 with `gitleaks dir` |

The wording and `AGENTS.md` quality Reviews are advisory; its FAIL and ERROR results remain visible without
blocking commits. Deterministic checks are blocking. Security and license checks
inspect the working tree at `check` and `HEAD` at `pre-push`, without Git history
or every pushed ref. Technical failures never establish PASS.

See complete import examples, parameters, evidence boundaries and limitations:

- [Repository conventions and Gemini](docs/repository-conventions.md)
- [Open-source software and license policy](docs/open-source-software.md)
- [Semantic Release baseline](docs/releases.md)
- [Security and scanner configuration](docs/security.md)
- [Compatibility and path migration](docs/migration.md)
- [Shared Renovate governor preset](docs/governor-updates.md)

## Validation

Tests cover single rule scripts or provider adapters only and live next to the code as
`test_*.py`. They use temporary local Git repositories and mocked HTTP and must never
call live providers or network APIs.

```sh
for test in $(find rules providers -name 'test_*.py'); do python3 -B "$test" || break; done
```

Skipped tests do not demonstrate successful validation. The repository currently
has no configured validation hooks or CI workflow. See [AGENTS.md](AGENTS.md) for change
boundaries and agent guidance.
