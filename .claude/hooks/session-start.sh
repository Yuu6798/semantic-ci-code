#!/bin/bash
# SessionStart hook: install the project + dev extras so that ruff,
# pytest, and the /wrap-up discipline-test gate (pytest tests/discipline/
# -q --no-cov, which needs the pytest-cov plugin) work in Claude Code on
# the web sessions. Synchronous so deps are guaranteed ready before the
# agent loop starts.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment; local dev
# machines manage their own virtualenv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Idempotent: pip install -e is safe to re-run and leverages the cached
# container state.
python -m pip install -e ".[dev]"
