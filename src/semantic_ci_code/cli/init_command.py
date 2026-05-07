from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.command_support import _internal_bug, _stderr, _usage_error
from semantic_ci_code.cli.exit_codes import SUCCESS

TARGET_TEMPLATE = """# semantic-ci target.yaml — declared change intent + constraints
intent: ""  # 1-line human-readable description of this PR
change:
  primary_kind: refactor  # feature | bugfix | refactor | test_update
  allowed_secondary_kinds: []
  scope:
    files: []
    modules: []
authorship:
  authors:
    - identity: ""
  declared_at: ""  # ISO-8601, e.g. 2026-05-05T12:00:00Z
# constraints: severity defaults to "hard"; "soft" or "info" weakens the gate.
constraints: []  # user constraints; templates are auto-expanded from primary_kind
"""


def run_init(args: Namespace) -> int:
    try:
        path = Path(args.path or ".semantic-ci/target.yaml")
        if path.exists() and not args.force:
            return _usage_error(
                FileExistsError(f"target file already exists: {path}; pass --force to overwrite")
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TARGET_TEMPLATE, encoding="utf-8")
        if not args.quiet:
            _stderr(f"created {path}")
        return SUCCESS
    except OSError as exc:
        return _usage_error(exc)
    except Exception as exc:
        return _internal_bug(exc, args)
