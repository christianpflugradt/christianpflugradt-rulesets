#!/bin/sh

# Conventional Commits 1.0.0
#
# Exit codes:
#   0 = PASS
#   1 = FAIL
#   2 = ERROR
#
# Usage:
#   Invoked by Hannes at commit-msg; the message path is HANNES_GIT_HOOK_ARG_1.

set -u

fail() {
    printf 'FAIL commit-message: %s\n' "$1" >&2
    exit 1
}

error() {
    printf 'ERROR commit-message: %s\n' "$1" >&2
    exit 2
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) \
    || error "Cannot resolve rule directory"

TYPES_FILE="$SCRIPT_DIR/commit-types.txt"

[ -f "$TYPES_FILE" ] \
    || error "Missing commit types file: $TYPES_FILE"

[ "${HANNES_GIT_HOOK:-}" = "commit-msg" ] \
    || error "Expected the commit-msg hook context"

[ "${HANNES_GIT_HOOK_ARG_COUNT:-}" = "1" ] \
    || error "Expected exactly one commit-msg hook argument"

MESSAGE_FILE=${HANNES_GIT_HOOK_ARG_1:-}
[ -n "$MESSAGE_FILE" ] || error "Missing commit-message file argument"

[ -f "$MESSAGE_FILE" ] \
    || error "Commit-message file does not exist: $MESSAGE_FILE"

[ -r "$MESSAGE_FILE" ] \
    || error "Cannot read commit-message file: $MESSAGE_FILE"

[ -n "${HANNES_PARAM_SCOPES_FILE:-}" ] \
    || error "Required parameter 'scopes_file' is missing"

SCOPES_FILE=$HANNES_PARAM_SCOPES_FILE

[ -f "$SCOPES_FILE" ] \
    || error "Scopes file does not exist: $SCOPES_FILE"

[ -r "$SCOPES_FILE" ] \
    || error "Cannot read scopes file: $SCOPES_FILE"

# Read the first line without losing its contents.
IFS= read -r HEADER < "$MESSAGE_FILE" || [ -n "$HEADER" ] \
    || fail "Commit message is empty"

# Conventional Commits header:
# <type>[optional scope][optional !]: <description>

case "$HEADER" in
    *": "*)
        PREFIX=${HEADER%%: *}
        DESCRIPTION=${HEADER#*: }
        ;;
    *)
        fail "Expected '<type>[optional scope][!]: <description>'"
        ;;
esac

[ -n "$DESCRIPTION" ] \
    || fail "Commit description must not be empty"

# Reject whitespace-only descriptions.
case "$DESCRIPTION" in
    *[![:space:]]*) ;;
    *) fail "Commit description must not be blank" ;;
esac

# Remove optional breaking-change marker.
case "$PREFIX" in
    *'!')
        PREFIX=${PREFIX%?}
        ;;
esac

TYPE=$PREFIX
SCOPE=

case "$PREFIX" in
    *'('*')')
        TYPE=${PREFIX%%(*}
        SCOPE=${PREFIX#*\(}
        SCOPE=${SCOPE%\)}
        [ -n "$SCOPE" ] || fail "Commit scope must not be empty"
        ;;
    *'('*|*')'*)
        fail "Invalid commit scope syntax"
        ;;
esac

[ -n "$TYPE" ] || fail "Commit type must not be empty"

# Validate type against the centrally maintained allowlist.
grep -Fqx -- "$TYPE" "$TYPES_FILE"
case $? in
    0) ;;
    1) fail "Commit type '$TYPE' is not allowed" ;;
    *) error "Cannot read commit types file" ;;
esac

# Validate optional scope against the consuming repository's allowlist.
if [ -n "$SCOPE" ]; then
    case "$SCOPE" in
        *'('*|*')'*) fail "Invalid commit scope syntax" ;;
    esac
    grep -Fqx -- "$SCOPE" "$SCOPES_FILE"
    case $? in
        0) ;;
        1) fail "Commit scope '$SCOPE' is not allowed" ;;
        *) error "Cannot read scopes file" ;;
    esac
fi

# This check validates the header. Body and footer contents are not inspected.

printf 'PASS commit-message\n'
exit 0
