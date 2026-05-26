from __future__ import annotations

from semantic_ci_code.ssp.delta import assign_sast_ordinals, compute_delta
from semantic_ci_code.ssp.models import SASTFinding, SCAFinding, SensorOutput, SourceSpan


def _sast(
    rule_id: str,
    *,
    text: str = "danger()",
    line: int = 1,
    severity: str = "high",
) -> SASTFinding:
    return SASTFinding(
        rule_id=rule_id,
        module_path="src/app.py",
        qualified_name="app.handler",
        normalized_text=text,
        source_span=SourceSpan(start_line=line, start_col=0, end_line=line, end_col=8),
        severity=severity,
    )


def _sca(package: str, version: str = "1.0", advisory: str = "CVE-1") -> SCAFinding:
    return SCAFinding(
        package_name=package,
        installed_version=version,
        advisory_id=advisory,
        severity="high",
    )


def test_compute_delta_partitions_added_removed_and_unchanged():
    baseline = SensorOutput(sensor_id="semgrep", findings=(_sast("keep"), _sast("remove")))
    candidate = SensorOutput(sensor_id="semgrep", findings=(_sast("keep"), _sast("add")))

    delta = compute_delta(baseline, candidate)

    assert delta.status == "fail"
    assert [finding.rule_id for finding in delta.added] == ["add"]
    assert [finding.rule_id for finding in delta.removed] == ["remove"]
    assert delta.unchanged_count == 1


def test_compute_delta_empty_baseline_marks_all_candidate_findings_added():
    delta = compute_delta(
        SensorOutput(sensor_id="pip-audit"),
        SensorOutput(sensor_id="pip-audit", findings=(_sca("django"),)),
    )

    assert [finding.package_name for finding in delta.added] == ["django"]
    assert delta.removed == ()
    assert delta.unchanged_count == 0


def test_compute_delta_empty_candidate_marks_all_baseline_findings_removed():
    delta = compute_delta(
        SensorOutput(sensor_id="pip-audit", findings=(_sca("django"),)),
        SensorOutput(sensor_id="pip-audit"),
    )

    assert delta.added == ()
    assert [finding.package_name for finding in delta.removed] == ["django"]
    assert delta.unchanged_count == 0
    assert delta.status == "pass"


def test_compute_delta_identical_inputs_have_only_unchanged_count():
    finding = _sast("same")

    delta = compute_delta(
        SensorOutput(sensor_id="semgrep", findings=(finding,)),
        SensorOutput(sensor_id="semgrep", findings=(finding,)),
    )

    assert delta.added == ()
    assert delta.removed == ()
    assert delta.unchanged_count == 1
    assert delta.status == "pass"


def test_compute_delta_error_sensor_becomes_unknown_without_findings():
    delta = compute_delta(
        SensorOutput(sensor_id="semgrep", findings=(_sast("old"),)),
        SensorOutput(sensor_id="semgrep", status="error", error_message="timeout"),
    )

    assert delta.status == "unknown"
    assert delta.added == ()
    assert delta.removed == ()
    assert delta.unchanged_count == 0
    assert delta.error_message == "timeout"


def test_ordinal_assignment_dedups_before_assignment_and_sorts_by_source_span():
    duplicate_late = _sast("dup", line=30)
    duplicate_early = _sast("dup", line=10)
    duplicate_early_again = _sast("dup", line=10)

    assigned = assign_sast_ordinals((duplicate_late, duplicate_early, duplicate_early_again))

    assert [finding.ordinal for finding in assigned] == [1, 0]
    assert assigned[0].fingerprint != assigned[1].fingerprint


def test_ordinal_assignment_preserves_spanless_findings_in_same_group():
    spanless = SASTFinding(
        rule_id="spanless",
        module_path="src/app.py",
        qualified_name="app.handler",
        normalized_text="danger()",
        severity="high",
    )

    assigned = assign_sast_ordinals((spanless, spanless))

    assert [finding.ordinal for finding in assigned] == [0, 1]
    assert assigned[0].fingerprint != assigned[1].fingerprint


def test_compute_delta_reports_multiple_spanless_candidate_findings():
    spanless = SASTFinding(
        rule_id="spanless",
        module_path="src/app.py",
        qualified_name="app.handler",
        normalized_text="danger()",
        severity="high",
    )

    delta = compute_delta(
        SensorOutput(sensor_id="semgrep"),
        SensorOutput(sensor_id="semgrep", findings=(spanless, spanless)),
    )

    assert len(delta.added) == 2
    assert [finding.ordinal for finding in delta.added] == [0, 1]


def test_ordinal_assignment_single_finding_group_gets_zero():
    assigned = assign_sast_ordinals((_sast("single"),))

    assert assigned[0].ordinal == 0
    assert assigned[0].fingerprint is not None


def test_virtual_hand_built_sensor_output_is_accepted():
    baseline = SensorOutput(sensor_id="virtual-semgrep")
    candidate = SensorOutput(sensor_id="virtual-semgrep", findings=(_sast("virtual"),))

    assert compute_delta(baseline, candidate).status == "fail"
