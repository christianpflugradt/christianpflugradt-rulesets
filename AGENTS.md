# Working on Please Behave governance

## Policy boundaries

- Read the Architectural Boundaries of the Please Behave
  [product vision](https://github.com/please-behave/cli/blob/main/docs/product-vision.md)
  before adding or changing a Rule or bundle.
- Bundles use only the built-in execution points (`pre-commit`, `commit-msg`,
  `pre-push`, `check`) and never declare custom points. `release` is the only custom
  point; consumers declare it for their own rules.
- Group rulesets by shared repository attributes and execution points. Extend an
  existing bundle when both match; do not create one ruleset per check.
- Repository conventions apply to every repo: public/private, software,
  documentation or personal coaching. Conventional Commits and the `AGENTS.md`
  size limit belong here. Keep this baseline lightweight: it runs at `pre-commit`
  and `check`, with commit rules overridden to `commit-msg`, and works through Git
  hooks without requiring CI.
- Open-source software adds approved licenses and the shared workflow-syntax, shell
  and dependency-audit checks. A license check alone does not justify a separate ruleset.
- Releasable open-source software adds the Semantic Release baseline.
- Admit a Rule only with a strong argument. A Rule that merely passes one command to local
  tooling, such as a formatter or linter in check mode, stays local to each repository: accept
  the redundancy instead of centrally managing tool choices. Rules backed by local scripts that
  may drift between repositories are decided individually. Do not dictate technology stacks; a
  stack-specific ruleset (for example Java applications, where Maven or Gradle may be used) is
  neither excluded nor assumed and needs its own case. This is maintainer advice for this
  catalog, not a requirement of Please Behave, which supports any setup.
- Separate domains sparingly. Security is an intentional independent bundle for
  visibility; discuss other new boundaries before introducing them.
- These are additive policy responsibilities. README distinguishes implemented
  checks from future requirements; do not silently implement the latter.

## Structure and implementation

- Put sets at `rulesets/<bundle>/config.toml`. Bundles follow repository attributes,
  not execution points; their `run_at` values are declared in the set. Each set defines
  one declarative bundle with repository-relative Rule paths.
- Keep Rule-specific code, prompts and reference data with `rule.toml` under
  `rules/checks/` or `rules/reviews/`. Put reusable helpers in `scripts/` and
  provider definitions and adapters together under `providers/<provider>/`.
- Keep offline tests in `tests/`, the catalog and setup in README, and detailed
  usage in `docs/`. Update definitions, tests and documentation together.
- Commands run in the consumer root. Resolve imported resources explicitly;
  never modify the immutable source cache or install dependencies during checks.
- Preserve PASS/FAIL/ERROR distinctions. FAIL (exit 1) is only a verdict about the
  checked subject; every crash, missing helper or tooling problem must exit 2
  through a catch-all guard around the entry point. Provider, tooling and evidence failures
  must not become PASS. Keep credentials and private diagnostics out of output.

## Changes and compatibility

- Keep solutions small, dependencies lean and all source/output in English.
- Before moving public import paths, verify affected consumers use reviewed full
  commit pins. Old commits preserve their old layouts. Migrate consumers only
  when explicitly requested; do not add duplicate compatibility bundles.
- Use published Please Behave for offline import/hook integration, with mocked
  network responses and synthetic credentials. Never call paid/live providers
  or network APIs from tests. Test affected behavior; configured Git hooks remain
  authoritative gates. Missing tools or skipped tests are validation limitations.
- Work on `main`; commit and push each coherent authorized change. Preserve
  unrelated edits, avoid history rewrites, and stop after a successful push.
