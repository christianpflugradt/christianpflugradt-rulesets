#!/bin/sh
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required for sensitive-files" >&2
  exit 2
fi
if [ -z "${HANNES_RULE_DIRECTORY:-}" ]; then
  echo "ERROR: HANNES_RULE_DIRECTORY is required" >&2
  exit 2
fi
exec python3 "$HANNES_RULE_DIRECTORY/check.py"
