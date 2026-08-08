from __future__ import annotations

import re

from ._helpers import REPO_ROOT

TRACKER = REPO_ROOT / "docs" / "dogfooding_findings_tracker.md"
README = REPO_ROOT / "README.md"
ROADMAP = REPO_ROOT / "ROADMAP.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


def _resolved_registry_size() -> int:
    text = TRACKER.read_text(encoding="utf-8")
    registry_ids = set(re.findall(r"^\| D(\d+) \|", text, flags=re.MULTILINE))
    resolved_ids = set(
        re.findall(
            r"^\| D(\d+) \|.*\| \*\*解決\*\* \|",
            text,
            flags=re.MULTILINE,
        )
    )
    assert registry_ids, "D-class tracker must contain registry rows"
    assert resolved_ids == registry_ids, "public closure claims require every D-class row resolved"
    return len(registry_ids)


def test_public_docs_match_closed_d_class_registry() -> None:
    resolved_count = _resolved_registry_size()

    assert f"all {resolved_count} D-class findings are now resolved" in README.read_text(
        encoding="utf-8"
    )
    assert f"all {resolved_count} D-class findings are resolved" in ROADMAP.read_text(
        encoding="utf-8"
    )
    assert "The D-class registry is closed" in CONTRIBUTING.read_text(encoding="utf-8")
