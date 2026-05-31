#!/bin/bash
# SessionStart hook: install the project + dev deps so that lint, test, and
# the /wrap-up discipline-test gate work in remote (Claude Code on the web)
# sessions. Synchronous so deps are guaranteed ready before the agent loop
# starts.
set -euo pipefail

# Only run in the remote (web) environment; local dev machines manage their
# own environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# SessionStart stdout is injected into the model context, so keep the
# installer's progress / "already satisfied" chatter out of it: capture all
# install output and only surface it (on stderr) if the install fails.
# Keep the install command idempotent so re-runs are cheap.
log="$(mktemp)"
if ! {{INSTALL_CMD}} >"$log" 2>&1; then
  echo "session-start: dependency install failed:" >&2
  cat "$log" >&2
  exit 1
fi
echo "session-start: dev dependencies ready"
