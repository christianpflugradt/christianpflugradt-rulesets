# Compatibility and migration

## Policy bundle restructuring

The repository is now `christianpflugradt/please-behave-governance`. New import
examples and the Renovate preset reference use that name. Existing consumer pins
are unchanged; the previous Git URL currently resolves to the renamed repository.
The local checkout directory can be renamed independently.

All sets now live under `rulesets/`. Consumers adopting the intermediate
`cb30851` layout must prefix their set paths with `rulesets/` when upgrading to
this layout. Provider paths and repository-relative Rule references stay unchanged.

Existing consumers pinned to full commits retain their configuration and behavior.
No consumer migration is part of this restructuring. New revisions use these
canonical paths; old aliases are not retained:

| Previous path | Canonical path | Meaning |
| --- | --- | --- |
| `commit-msg/conventional-commits` | `rulesets/commit-msg/repository-conventions` | Universal conventions, unchanged syntax Check and advisory Review |
| `repository-conventions`, `multi-point/license` | `rulesets/multi-point/open-source-software` | License policy belongs to open-source software |
| `release/releasable-project` | `rulesets/multi-point/releasable-open-source-software` | Existing release contract, unchanged points and parameters |
| `multi-point/security` | `rulesets/multi-point/security` | Unchanged independent security bundle |
| `release/readiness` | Retired | Legacy mixed bundle; full-commit pins retain it |

The retired readiness set combined CI proof, security and license checks. It is
not an exact alias for the release contract. Any future migration must choose the
applicable canonical bundles and explicitly review coverage and parameters.
`github-ci-success` remains a reusable Rule and supplies the release contract's
readiness implementation.

The Gemini provider path and ID stay `providers/gemini-flash-lite` and
`gemini-flash-lite`; its adapter now lives in that package as `adapter.py`.
The release contract still exports `PLEASE_RELEASE_GUARD` for consumers to load;
its target now lives in `scripts/release-guard.mjs`. Consumers must use the
exported path rather than hard-code source-layout details.

Update pins and paths together only during an explicitly authorized migration.
Revalidate parameters and plans with the published governor before adoption.
The Renovate preset remains at `renovate-governor.json` with unchanged contents;
its documented preset URL uses the renamed repository.

## Historical runtime compatibility

This revision uses the Please Behave `PLEASE_*` runtime environment and `.please/`
configuration. Existing Hannes consumers must retain the last compatible full
commit pin `86c1a09519de6e848e6f8a0110427ca8d136dd1c`. Historical pins remain usable.
For a runtime-only migration without wording reviews, published Please Behave
v0.1.0+ and pin `4825ec7d61ea01bd40cef3a126f107ef924f1666` retain the former
syntax-only set. Migrate the consumer to `.please/` and run `please sync`.

