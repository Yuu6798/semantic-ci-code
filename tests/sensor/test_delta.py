from __future__ import annotations

from semantic_ci_code.sensor.delta import compute_security_delta
from semantic_ci_code.sensor.models import SensorState

from .helpers import provenance, sast_finding, sca_finding, sensor_state


def test_compute_security_delta_partitions_added_removed_and_unchanged():
    unchanged = sast_finding("same.rule", severity="info")
    removed = sast_finding("removed.rule", severity="medium")
    added = sast_finding("added.rule", severity="high")
    baseline = sensor_state(findings=(unchanged, removed))
    candidate = sensor_state(findings=(unchanged, added))

    delta = compute_security_delta(baseline, candidate)
    semgrep = delta.deltas_by_sensor["semgrep"]

    assert semgrep.status == "fail"
    assert semgrep.added == (added,)
    assert semgrep.removed == (removed,)
    assert semgrep.unchanged_count == 1
    assert delta.aggregate_status == "fail"


def test_info_only_added_findings_keep_sensor_delta_pass():
    added = sast_finding("info.rule", severity="info")
    delta = compute_security_delta(sensor_state(findings=()), sensor_state(findings=(added,)))

    assert delta.deltas_by_sensor["semgrep"].status == "pass"
    assert delta.aggregate_status == "pass"


def test_provenance_drift_blocks_sensor_comparison_as_unknown():
    """Default G-1 policy treats ruleset drift as comparison-blocking drift."""

    finding = sast_finding("same.rule", severity="high")
    baseline = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:old"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:new"),),
        findings=(finding,),
    )

    delta = compute_security_delta(baseline, candidate)
    semgrep = delta.deltas_by_sensor["semgrep"]

    assert semgrep.status == "unknown"
    assert semgrep.provenance_changed is True
    assert semgrep.added == ()
    assert semgrep.removed == ()
    assert "ruleset_hash" in (semgrep.error_message or "")
    assert delta.aggregate_status == "unknown"


def test_sensor_version_drift_is_ignored_by_default_policy():
    """Planning 2.3 default keeps require_same_sensor_version=false in G-1."""

    finding = sast_finding("same.rule", severity="info")
    baseline = sensor_state(
        provenances=(provenance(sensor_version="tool-1"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(sensor_version="tool-2"),),
        findings=(finding,),
    )

    delta = compute_security_delta(baseline, candidate)

    assert delta.deltas_by_sensor["semgrep"].status == "pass"
    assert delta.deltas_by_sensor["semgrep"].provenance_changed is False
    assert delta.deltas_by_sensor["semgrep"].unchanged_count == 1


def test_explicit_drift_fields_can_include_sensor_version():
    finding = sast_finding("same.rule", severity="info")
    baseline = sensor_state(
        provenances=(provenance(sensor_version="tool-1"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(sensor_version="tool-2"),),
        findings=(finding,),
    )

    delta = compute_security_delta(
        baseline,
        candidate,
        drift_fields=frozenset({"adapter_version", "identity_algorithm_version", "sensor_version"}),
    )

    assert delta.deltas_by_sensor["semgrep"].status == "unknown"
    assert delta.deltas_by_sensor["semgrep"].provenance_changed is True
    assert "sensor_version" in (delta.deltas_by_sensor["semgrep"].error_message or "")


def test_provenance_drift_reason_orders_changed_fields_deterministically():
    baseline = sensor_state(
        provenances=(
            provenance(
                adapter_version="adapter-a",
                ruleset_hash="sha256:rules-a",
                sensor_version="tool-a",
            ),
        ),
        findings=(),
    )
    candidate = sensor_state(
        provenances=(
            provenance(
                adapter_version="adapter-b",
                ruleset_hash="sha256:rules-b",
                sensor_version="tool-b",
            ),
        ),
        findings=(),
    )

    delta = compute_security_delta(
        baseline,
        candidate,
        drift_fields=frozenset({"sensor_version", "ruleset_hash", "adapter_version"}),
    )

    assert (
        delta.deltas_by_sensor["semgrep"].error_message
        == "sensor provenance changed: adapter_version, ruleset_hash, sensor_version"
    )


def test_explicit_drift_fields_can_relax_ruleset_hash_drift():
    finding = sast_finding("same.rule", severity="info")
    baseline = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:old"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:new"),),
        findings=(finding,),
    )

    delta = compute_security_delta(
        baseline,
        candidate,
        drift_fields=frozenset({"adapter_version", "identity_algorithm_version"}),
    )

    assert delta.deltas_by_sensor["semgrep"].status == "pass"
    assert delta.deltas_by_sensor["semgrep"].provenance_changed is False
    assert delta.deltas_by_sensor["semgrep"].unchanged_count == 1


def test_one_sided_sensor_is_unknown_and_marks_provenance_changed():
    baseline = sensor_state(provenances=(provenance(sensor_id="semgrep"),), findings=())
    candidate = sensor_state(
        provenances=(
            provenance(sensor_id="semgrep"),
            provenance(sensor_id="pip-audit", advisory_db_hash="sha256:db"),
        ),
        findings=(),
    )

    delta = compute_security_delta(baseline, candidate)
    pip_audit = delta.deltas_by_sensor["pip-audit"]

    assert pip_audit.status == "unknown"
    assert pip_audit.provenance_changed is True
    assert "one side" in (pip_audit.error_message or "")
    assert delta.aggregate_status == "unknown"


def test_non_complete_sensor_is_unknown_without_provenance_drift():
    baseline = sensor_state(
        provenances=(provenance(status="error", error_message="semgrep failed"),),
        findings=(),
    )
    candidate = sensor_state(provenances=(provenance(),), findings=())

    delta = compute_security_delta(baseline, candidate)
    semgrep = delta.deltas_by_sensor["semgrep"]

    assert semgrep.status == "unknown"
    assert semgrep.provenance_changed is False
    assert semgrep.error_message == "semgrep failed"


def test_aggregate_precedence_unknown_over_fail_over_pass():
    semgrep_added = sast_finding("bad.rule", severity="high")
    pip_added = sca_finding(severity="info")
    baseline = sensor_state(
        provenances=(
            provenance(sensor_id="semgrep"),
            provenance(sensor_id="pip-audit", advisory_db_hash="sha256:db-old"),
        ),
        findings=(),
    )
    candidate = sensor_state(
        provenances=(
            provenance(sensor_id="semgrep"),
            provenance(sensor_id="pip-audit", advisory_db_hash="sha256:db-new"),
        ),
        findings=(semgrep_added, pip_added),
    )

    delta = compute_security_delta(baseline, candidate)

    assert delta.deltas_by_sensor["semgrep"].status == "fail"
    assert delta.deltas_by_sensor["pip-audit"].status == "unknown"
    assert delta.aggregate_status == "unknown"


def test_hand_built_json_states_compare_without_extractor_or_adapter_execution():
    components = (
        "v1",
        "sast",
        "semgrep",
        "python.security.eval",
        "src/app.py",
        "src.app.handler",
        "eval(user_input)",
        "0",
    )
    candidate_dict = {
        "identity_algorithm_version": "v1",
        "provenance_by_sensor": {
            "semgrep": {
                "sensor_id": "semgrep",
                "sensor_version": "1.0.0",
                "adapter_version": "adapter-1",
                "identity_algorithm_version": "v1",
                "ruleset_hash": "sha256:rules",
                "status": "complete",
            }
        },
        "findings": [
            {
                "category": "sast",
                "sensor_id": "semgrep",
                "canonical_id": "v1:0000000000000000",
                "identity_components": components,
                "severity": "high",
                "message": "finding",
                "rule_id": "python.security.eval",
                "module_path": "src/app.py",
                "qualified_name": "src.app.handler",
                "normalized_text": "eval(user_input)",
                "ordinal": 0,
            }
        ],
    }
    canonical_id = sast_finding("python.security.eval").canonical_id
    candidate_dict["findings"][0]["canonical_id"] = canonical_id
    baseline = SensorState.model_validate(
        {
            "identity_algorithm_version": "v1",
            "provenance_by_sensor": candidate_dict["provenance_by_sensor"],
            "findings": [],
        }
    )
    candidate = SensorState.model_validate(candidate_dict)

    delta = compute_security_delta(baseline, candidate)

    assert delta.deltas_by_sensor["semgrep"].status == "fail"
    assert delta.deltas_by_sensor["semgrep"].added[0].canonical_id == canonical_id
