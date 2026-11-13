# Security

The `rulesets/security` set runs two blocking checks at `check` and `pre-push`:

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
git = "https://github.com/christianpflugradt/please-behave-governance.git"
path = "rulesets/security"
ref = "<FULL_REVIEWED_COMMIT_SHA>"
```

Pin a full commit hash for reproducible imports. Run `please sync` to resolve
the import and install the managed pre-push hook, then run
`please run --at check` to inspect the working tree explicitly.
See the scanner configuration and limitations below.

## Snapshot selection

The security and license rules take the snapshot from the run context's execution
point: `pre-commit` and `check` use `worktree`, `pre-push` uses `head`. Any other
execution point is ERROR. Neither selection scans history.

## Scanner configuration and limitations

The `rulesets/security` ruleset uses `gitleaks dir` on a temporary
snapshot. `check` copies current tracked and nonignored untracked files;
`pre-push` reads blobs from `HEAD` directly, without export attributes or history.

Gitleaks uses `.gitleaks.toml` and `.gitleaksignore` from that snapshot, or its
built-in detection rules when no configuration is present. `GITLEAKS_CONFIG` and
`GITLEAKS_CONFIG_TOML` are ignored so an external file or working-tree override
cannot change the committed scan. Use Gitleaks' standard configuration allowlists
for false positives. Keep any allowlists narrow and review their changes.

File contents behind symlinks are never scanned, including when a working-tree
directory has been replaced by a symlink. The filename check still rejects a
prohibited symlink name. Git submodules and other nonregular entries cause the
content scanner to report ERROR because their contents are outside its snapshot
coverage. Git LFS files in `HEAD` are scanned as their committed pointer blobs.

PASS exits 0; detected violations exit 1; technical errors exit 2. Missing tools,
Git failures, invalid configuration, missing/malformed scanner reports and
inconsistent scanner results cannot produce PASS. Internally, Gitleaks receives
a dedicated findings exit code to distinguish detections from tool errors.
Findings show escaped filenames and rule IDs, without secret values or matching
lines. Raw tool output is suppressed because it may contain sensitive data.
Please Behave enforces the check's configured timeout.

These checks are complementary: a secret-free `.env` still violates the filename
policy, while a secret in an ordinary source file can fail the content scan.
Allowed template filenames remain subject to secret scanning. Filename matching
and Gitleaks detection cannot establish that every secret has been found.
Imported rules execute with the consumer's permissions; trust their source and
pin their revision.
