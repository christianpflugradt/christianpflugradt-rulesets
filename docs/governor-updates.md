# Governor updates with Renovate

Extend `github>christianpflugradt/please-behave-governance:renovate-governor` in
`renovate.json`. Declare the exact published governor in `mise.toml`:

```toml
[tools]
"github:please-behave/cli" = "<exact published version>"
```

Renovate's native mise manager tracks this entry using GitHub Releases. The shared
preset applies the governor update policy without a custom version-file parser.
Renovate opens PRs for newer stable
governors, including major versions, and auto-merges after checks pass. These
updates have no minimum release age; prereleases remain excluded. The preset
uses Renovate-managed PR auto-merge, requires passing checks and leaves ordinary
dependency cooldowns to each project. Updates occur on Renovate's runs, so this
does not promise an instantaneous update when a release is published.

Local package rules are applied after preset rules. Exclude `please-behave/cli`
from any local cooldown or post-upgrade rule that would override this exception,
using `"matchPackageNames": ["!please-behave/cli"]`. Do not add a local governor
version extraction or auto-merge implementation. Workflows read the same mise
entry and install that exact published binary before checks; `mise install`
provides it locally through the GitHub backend with checksum and available
artifact-attestation verification. The preset follows this repository's default branch, like other
shared Renovate policies; Please Behave runtime imports retain immutable pins.
