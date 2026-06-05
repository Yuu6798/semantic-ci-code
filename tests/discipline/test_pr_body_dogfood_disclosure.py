"""PR body dogfooding disclosure discipline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_pr_body_dogfood import DogfoodDisclosureError, main, validate_pr_body


def _body(section: str) -> str:
    return f"""# Completion Summary: TEST

## Phase
Example

{section}

## Tests
- Result: pass
"""


def test_pr_body_dogfood_performed_requires_evidence() -> None:
    validate_pr_body(
        _body(
            """## Dogfooding
- Status: performed
- Commands:
  - `semantic-ci init --recipe security:deny-dangerous-imports`
- Result: generated target.yaml compiled successfully
"""
        )
    )


def test_pr_body_dogfood_skipped_requires_reason() -> None:
    validate_pr_body(
        _body(
            """## Dogfooding
- Status: skipped
- Reason: pure model-only change; no CLI or authoring surface changed
"""
        )
    )


@pytest.mark.parametrize(
    ("section", "expected"),
    (
        ("", "must include `## Dogfooding`"),
        (
            """## Dogfooding
- Commands: `semantic-ci init`
""",
            "must include `Status: performed` or `Status: skipped`",
        ),
        (
            """## Dogfooding
- Status: performed
- Commands: <commands run>
""",
            "must include non-empty dogfood evidence",
        ),
        (
            """## Dogfooding
- Status: performed
""",
            "must include non-empty dogfood evidence",
        ),
        (
            """## Dogfooding
- Status: skipped
""",
            "must include a non-empty `Reason:`",
        ),
    ),
)
def test_pr_body_dogfood_disclosure_rejects_missing_required_parts(
    section: str, expected: str
) -> None:
    with pytest.raises(DogfoodDisclosureError) as exc_info:
        validate_pr_body(_body(section))
    assert expected in str(exc_info.value)


def test_pr_body_dogfood_event_path_noops_for_non_pr_event(tmp_path: Path) -> None:
    event = tmp_path / "push.json"
    event.write_text(json.dumps({"ref": "refs/heads/main"}), encoding="utf-8")
    assert main(["--event-path", str(event)]) == 0


def test_pr_body_dogfood_event_path_validates_pull_request_body(tmp_path: Path) -> None:
    event = tmp_path / "pull_request.json"
    event.write_text(json.dumps({"pull_request": {"body": _body("")}}), encoding="utf-8")
    assert main(["--event-path", str(event)]) == 1
