# Security scanner configuration

The [Security Rule Set](README.md#security) uses `gitleaks dir` on a temporary
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
Hannes enforces the check's configured timeout.

These checks are complementary: a secret-free `.env` still violates the filename
policy, while a secret in an ordinary source file can fail the content scan.
Allowed template filenames remain subject to secret scanning. Filename matching
and Gitleaks detection cannot establish that every secret has been found.
Imported rules execute with the consumer's permissions; trust their source and
pin their revision.
