#!/bin/sh
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for secret-scan" >&2
  exit 2
fi
if [ -z "${PLEASE_RULE_DIRECTORY:-}" ]; then
  echo "ERROR: PLEASE_RULE_DIRECTORY is required" >&2
  exit 2
fi
exec python3 "$PLEASE_RULE_DIRECTORY/check.py"
