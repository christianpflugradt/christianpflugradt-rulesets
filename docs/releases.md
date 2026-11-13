# Releasable open-source software

Import `rulesets/releasable-open-source-software` in addition to the other bundles.
It runs the blocking `semantic-release` Check at `pre-push` (`HEAD`) and `check`
(working tree). Example for the consumer's `.please/config.toml`:

```toml
[[imports]]
git = "https://github.com/christianpflugradt/please-behave-governance.git"
path = "rulesets/releasable-open-source-software"
ref = "<FULL_REVIEWED_COMMIT_SHA>"

[imports.rule_parameters.semantic-release]
tag_format = "v${version}"
```

`tag_format` is required because parameters have no defaults. A repository with
legacy tags declares `${version}`.

## Semantic Release baseline

The Check evaluates `release.config.mjs` with Node in an isolated directory, so the
module must be self-contained, and reads `package.json` and `package-lock.json`.
It requires Python 3.9+, Git and Node 24+. Requirements:

- `release.config.mjs` is the only configuration source: no `.releaserc*`, no other
  `release.config.*` and no `release` key in `package.json`.
- Only `branches`, `tagFormat`, `repositoryUrl` and `plugins` are set. `branches` is
  `["main"]`. `tagFormat` equals `tag_format`. `repositoryUrl` is optional.
- Plugins are the commit analyzer, the release notes generator, optional local
  plugins (plain `./path.mjs` files that must exist) and `@semantic-release/github`,
  in that order. Changelog, Git and npm plugins are therefore excluded.
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

## Release task

The blocking `mise-release` Check requires a `release` task in the root `mise.toml` (same
rules as the [Mise baseline](repository-conventions.md#mise-baseline); it needs Python 3.11+).
Its body is the repository's own; normally it starts the release workflow, for example
`gh workflow run release.yml --ref main`. The task runs on the remote `main`, never on local
state.
