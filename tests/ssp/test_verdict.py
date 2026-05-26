from __future__ import annotations

from semantic_ci_code.ssp.models import SCAFinding, SSPDelta
from semantic_ci_code.ssp.verdict import aggregate_verdict, build_verdict, verdict_for_delta


def _delta(sensor_id: str, status: str = "pass", *, severity: str = "high") -> SSPDelta:
    added = ()
    if status != "unknown":
        added = (
            SCAFinding(
                package_name=f"{sensor_id}-pkg",
                installed_version="1",
                advisory_id="CVE-1",
                severity=severity,
                fingerprint=f"{sensor_id[:4]:0<16}"[:16],
            ),
        )
    return SSPDelta(
        sensor_id=sensor_id,
        status=status,
        added=added,
        removed=(),
        unchanged_count=0,
    )


def test_verdict_precedence_unknown_over_fail_over_pass():
    assert aggregate_verdict(["pass", "fail", "unknown"]) == "unknown"
    assert aggregate_verdict(["pass", "fail"]) == "fail"
    assert aggregate_verdict(["pass"]) == "pass"


def test_aggregate_verdict_empty_returns_pass():
    assert aggregate_verdict([]) == "pass"


def test_error_sensor_delta_verdict_unknown():
    delta = SSPDelta(sensor_id="semgrep", status="unknown", unchanged_count=0)

    assert verdict_for_delta(delta) == "unknown"


def test_info_only_added_findings_pass():
    assert verdict_for_delta(_delta("info", severity="info")) == "pass"


def test_mixed_severity_added_findings_fail():
    assert verdict_for_delta(_delta("high", severity="high")) == "fail"


def test_build_verdict_sorts_sensor_ids_for_determinism():
    verdict = build_verdict(
        (
            _delta("zeta", severity="info"),
            _delta("alpha", status="fail", severity="high"),
        )
    )

    assert list(verdict.sensor_verdicts) == ["alpha", "zeta"]
    assert verdict.aggregate_verdict == "fail"


def test_build_verdict_uses_delta_status_as_canonical_sensor_verdict():
    verdict = build_verdict((_delta("semgrep", status="fail", severity="info"),))

    assert verdict.sensor_verdicts == {"semgrep": "fail"}
    assert verdict.aggregate_verdict == "fail"
