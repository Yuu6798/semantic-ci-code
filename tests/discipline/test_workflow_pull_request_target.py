"""Guard the security invariants of `pull_request_target` workflows.

`pull_request_target` runs with base-repo permissions on events from
untrusted forks. The classic escalation paths are (1) checking out PR head
code and executing anything from it, (2) interpolating attacker-controlled
event data into `run:` shell via `${{ ... }}`, and (3) granting write
permissions. Workflows must read event data from $GITHUB_EVENT_PATH instead.

See the invariant comment at the top of
`.github/workflows/pr-body-discipline.yml`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# PyYAML parses the bare key `on` as boolean True (YAML 1.1).
_TRIGGER_KEYS = ("on", True)
_READONLY_PERMISSION_VALUES = frozenset({"read", "none"})


def pull_request_target_violations(workflow_text: str) -> list[str]:
    """Return invariant violations for one workflow document."""

    data = yaml.safe_load(workflow_text)
    if not isinstance(data, dict):
        return []
    if not _uses_pull_request_target(data):
        return []

    violations: list[str] = []
    permissions = data.get("permissions")
    if not _permissions_are_read_only(permissions):
        violations.append(
            "pull_request_target workflow must declare workflow-level read-only "
            "permissions (e.g. `permissions: contents: read`)"
        )

    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_permissions = job.get("permissions")
            if job_permissions is not None and not _permissions_are_read_only(job_permissions):
                violations.append(f"job {job_name!r} declares non-read-only permissions")
            for step in job.get("steps") or ():
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith("actions/checkout"):
                    violations.append(
                        f"job {job_name!r} checks out code via {uses!r}; "
                        "pull_request_target workflows must not check out PR code"
                    )
                run = step.get("run")
                if isinstance(run, str) and "${{" in run:
                    violations.append(
                        f"job {job_name!r} interpolates `${{{{ ... }}}}` inside a run block; "
                        "read event data from $GITHUB_EVENT_PATH instead"
                    )
    return violations


def _uses_pull_request_target(data: dict[str, Any]) -> bool:
    for key in _TRIGGER_KEYS:
        triggers = data.get(key)
        if triggers is None:
            continue
        if isinstance(triggers, str):
            return triggers == "pull_request_target"
        if isinstance(triggers, list):
            return "pull_request_target" in triggers
        if isinstance(triggers, dict):
            return "pull_request_target" in triggers
    return False


def _permissions_are_read_only(permissions: object) -> bool:
    if isinstance(permissions, dict):
        return bool(permissions) and all(
            value in _READONLY_PERMISSION_VALUES for value in permissions.values()
        )
    if isinstance(permissions, str):
        return permissions in {"read-all", "{}"}
    return False


def _workflow_files() -> tuple[Path, ...]:
    return tuple(sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml")))


def test_repo_has_workflow_files():
    assert _workflow_files(), f"no workflow files found under {WORKFLOWS_DIR}"


@pytest.mark.parametrize(
    "workflow_path",
    _workflow_files(),
    ids=lambda path: path.name,
)
def test_pull_request_target_workflows_keep_security_invariants(workflow_path: Path):
    violations = pull_request_target_violations(workflow_path.read_text(encoding="utf-8"))
    assert not violations, f"{workflow_path.name}: {violations}"


_VIOLATING_CHECKOUT = """\
on:
  pull_request_target:
permissions:
  contents: read
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
"""

_VIOLATING_INTERPOLATION = """\
on:
  pull_request_target:
permissions:
  contents: read
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ github.event.pull_request.title }}"
"""

_VIOLATING_PERMISSIONS = """\
on:
  pull_request_target:
permissions:
  contents: write
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""

_VIOLATING_MISSING_PERMISSIONS = """\
on:
  pull_request_target:
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""

_SAFE_PULL_REQUEST_TRIGGER = """\
on:
  pull_request:
jobs:
  fine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ matrix.python-version }}"
"""


@pytest.mark.parametrize(
    ("workflow_text", "expected_fragment"),
    [
        (_VIOLATING_CHECKOUT, "must not check out PR code"),
        (_VIOLATING_INTERPOLATION, "GITHUB_EVENT_PATH"),
        (_VIOLATING_PERMISSIONS, "read-only"),
        (_VIOLATING_MISSING_PERMISSIONS, "read-only"),
    ],
    ids=["checkout", "run-interpolation", "write-permissions", "missing-permissions"],
)
def test_checker_detects_violating_workflows(workflow_text: str, expected_fragment: str):
    violations = pull_request_target_violations(workflow_text)
    assert violations, "expected the checker to flag this workflow"
    assert any(expected_fragment in violation for violation in violations), violations


def test_checker_ignores_plain_pull_request_workflows():
    assert pull_request_target_violations(_SAFE_PULL_REQUEST_TRIGGER) == []
