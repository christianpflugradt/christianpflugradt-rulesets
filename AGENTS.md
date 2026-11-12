# Working on Please Behave governance

## Policy boundaries

- Group rulesets by shared repository attributes and execution points. Extend an
  existing bundle when both match; do not create one ruleset per check.
- Repository conventions apply to every repo: public/private, software,
  documentation or personal coaching. Conventional Commits and the `AGENTS.md`
  size limit belong here. Keep this baseline lightweight: it runs at `pre-commit`
  and `check`, with commit rules overridden to `commit-msg`, and works through Git
  hooks without requiring CI.
- Open-source software adds approved licenses and aligned `ci.yml` quality
  assurance. A license check alone does not justify a separate ruleset.
- Releasable open-source software adds aligned `release.yml` governance and
  successful CI evidence for the release source SHA.
- Separate domains sparingly. Security is an intentional independent bundle for
  visibility; discuss other new boundaries before introducing them.
- These are additive policy responsibilities. README distinguishes implemented
  checks from future requirements; do not silently implement the latter.

## Structure and implementation

- Put sets at `rulesets/<execution-point>/<bundle>/config.toml` or
  `rulesets/multi-point/<bundle>/config.toml` according to their actual `run_at`
  values. Each set defines one declarative bundle with repository-relative Rule paths.
- Keep Rule-specific code, prompts and reference data with `rule.toml` under
  `rules/checks/` or `rules/reviews/`. Put reusable helpers in `scripts/` and
  provider definitions and adapters together under `providers/<provider>/`.
- Keep offline tests in `tests/`, the catalog and setup in README, and detailed
  usage in `docs/`. Update definitions, tests and documentation together.
- Commands run in the consumer root. Resolve imported resources explicitly;
  never modify the immutable source cache or install dependencies during checks.
- Preserve PASS/FAIL/ERROR distinctions. Provider, tooling and evidence failures
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
