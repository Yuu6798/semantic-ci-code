from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._helpers import REPO_ROOT

JSON_SCHEMA_DOC = REPO_ROOT / "docs" / "json_schema.md"
FIXTURES = Path(__file__).parent / "fixtures"

# Each CLI JSON envelope pairs its `schema_version` constant (the producer /
# source of truth) with the doc anchor in docs/json_schema.md that must mirror
# the constant's live value. `doc_anchor` carries a `{version}` placeholder
# filled with the value read back from source.
#
# This grounds the "producer output shape" against its documented mirror: when
# code bumps a schema_version without updating the doc (or vice versa), the
# formatted anchor stops appearing and the check fails. Adding a new envelope
# means adding a row here AND documenting it -- itself the intended discipline.
ENVELOPES = (
    {
        "name": "verdict/compile",
        "source": "src/semantic_ci_code/cli/output/json_formatter.py",
        "constant": "SCHEMA_VERSION",
        "doc_anchor": '| `schema_version` | CLI JSON schema version. Currently `"{version}"`. |',
    },
    {
        "name": "compile-repair",
        "source": "src/semantic_ci_code/cli/commands/compile_repair.py",
        "constant": "_COMPILE_REPAIR_SCHEMA_VERSION",
        "doc_anchor": (
            '| `schema_version` | Compile-repair envelope version. Currently `"{version}"`. |'
        ),
    },
    {
        "name": "validate-plan",
        "source": "src/semantic_ci_code/cli/commands/validate_plan.py",
        "constant": "_VALIDATE_PLAN_SCHEMA_VERSION",
        "doc_anchor": (
            '| `schema_version` | Validate-plan envelope version. Currently `"{version}"`. |'
        ),
    },
    {
        "name": "target-doctor advisory",
        "source": "src/semantic_ci_code/cli/output/doctor_json.py",
        "constant": "DOCTOR_ADVISORY_SCHEMA_VERSION",
        "doc_anchor": '| `schema_version` | Always `"{version}"`. |',
    },
    {
        "name": "target-catalog",
        "source": "src/semantic_ci_code/authoring/catalog.py",
        "constant": "CATALOG_SCHEMA_VERSION",
        "doc_anchor": '"schema_version": "{version}"',
    },
)


def read_constant_value(source_rel: str, constant: str) -> str:
    """Return the string literal assigned to `constant` in `source_rel`."""

    text = (REPO_ROOT / source_rel).read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(constant)}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise AssertionError(
            f"Constant {constant} not found in {source_rel}; the schema-sync "
            "discipline check cannot ground the producer output shape."
        )
    return match.group(1)


def schema_version_drift(doc_text: str) -> list[str]:
    violations: list[str] = []
    for envelope in ENVELOPES:
        version = read_constant_value(envelope["source"], envelope["constant"])
        anchor = envelope["doc_anchor"].format(version=version)
        if anchor not in doc_text:
            violations.append(
                f'{envelope["name"]}: code {envelope["constant"]}="{version}" '
                f"but docs/json_schema.md is missing anchor: {anchor!r}"
            )
    return violations


def _assert_no_schema_drift(doc_text: str, *, source: str) -> None:
    violations = schema_version_drift(doc_text)
    if not violations:
        return
    details = "\n".join(f"  - {item}" for item in violations)
    raise AssertionError(
        f"{source} schema_version doc/code drift:\n{details}\n"
        "Fix: update docs/json_schema.md so the documented current version "
        "mirrors the producer constant (or revert the unintended code bump)."
    )


def test_json_schema_doc_mirrors_code_constants() -> None:
    _assert_no_schema_drift(
        JSON_SCHEMA_DOC.read_text(encoding="utf-8"),
        source="docs/json_schema.md",
    )


def test_schema_sync_detects_drift_fixture() -> None:
    text = (FIXTURES / "json_schema_stale_version.md").read_text(encoding="utf-8")
    assert schema_version_drift(text)
    with pytest.raises(AssertionError, match="schema_version doc/code drift"):
        _assert_no_schema_drift(text, source="fixture")


def test_read_constant_missing_raises() -> None:
    with pytest.raises(AssertionError, match="cannot ground the producer"):
        read_constant_value(
            "src/semantic_ci_code/cli/output/json_formatter.py",
            "DEFINITELY_NOT_A_REAL_CONSTANT",
        )
