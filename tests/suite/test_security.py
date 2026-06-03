from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from semantic_ci_code.framework.security_policy import (
    AddedFindingsPolicy,
    FindingsPolicy,
    RulesPolicy,
    ScannerPolicy,
    SecurityPolicy,
    SeverityFilter,
    Suppression,
)
from semantic_ci_code.sensor.models import SensorState, canonical_id_for_identity
from semantic_ci_code.suite.security import (
    _drift_fields_for_scanner,
    evaluate_security,
    evaluate_security_detail,
)

from .helpers import provenance, sast_finding, sca_finding, sensor_state

AS_OF = dt.date(2026, 6, 3)


def _suppression_for(finding, *, expires: dt.date = dt.date(2026, 9, 1)) -> Suppression:
    return Suppression(
        canonical_id=finding.canonical_id,
        identity_components=finding.identity_components,
        reason="accepted false positive",
        expires=expires,
        owner="security-team",
    )


def test_evaluate_security_fails_on_denied_added_severity():
    added = sast_finding("python.security.eval", severity="high")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        )
    )

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_active_suppression_turns_fail_into_pass():
    added = sast_finding("python.security.eval", severity="high")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        ),
        suppressions=(_suppression_for(added),),
    )

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "pass"


def test_evaluate_security_detail_matches_wrapper_and_retains_suppressed_findings():
    added = sast_finding("python.security.eval", severity="high")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        ),
        suppressions=(_suppression_for(added),),
    )
    baseline = sensor_state(findings=())
    candidate = sensor_state(findings=(added,))

    detail = evaluate_security_detail(policy, baseline, candidate, as_of=AS_OF)

    assert detail.status == evaluate_security(policy, baseline, candidate, as_of=AS_OF)
    assert detail.as_of == AS_OF
    assert detail.global_count_violated is False
    assert len(detail.sensors) == 1
    sensor = detail.sensors[0]
    assert sensor.sensor_id == "semgrep"
    assert sensor.status == "pass"
    assert sensor.added == ()
    assert sensor.suppressed == (added,)
    assert sensor.removed == ()
    assert sensor.drift_reason is None
    assert sensor.unchanged_count == 0


def test_evaluate_security_expired_suppression_does_not_filter_added_finding():
    added = sast_finding("python.security.eval", severity="high")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        ),
        suppressions=(_suppression_for(added, expires=dt.date(2026, 6, 2)),),
    )

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_relaxes_default_floor_with_severity_filter():
    added = sast_finding("python.security.medium", severity="medium")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        )
    )

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "pass"


def test_evaluate_security_max_count_can_fail_info_only_added_finding():
    added = sca_finding("example", severity="info")
    policy = SecurityPolicy(findings=FindingsPolicy(added=AddedFindingsPolicy(max_count=0)))

    status = evaluate_security(
        policy,
        sensor_state(provenances=(provenance(sensor_id="pip-audit"),), findings=()),
        sensor_state(
            provenances=(provenance(sensor_id="pip-audit"),),
            findings=(added,),
        ),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_max_count_does_not_replace_default_floor():
    added = sast_finding("critical.rule", severity="critical")
    policy = SecurityPolicy(findings=FindingsPolicy(added=AddedFindingsPolicy(max_count=10)))

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_deny_added_does_not_replace_default_floor():
    added = sast_finding("other.rule", severity="high")
    policy = SecurityPolicy(rules=RulesPolicy(deny_added=("sql-injection",)))

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_deny_added_rule_is_severity_independent():
    added = sast_finding("sql-injection", severity="info")
    policy = SecurityPolicy(rules=RulesPolicy(deny_added=("sql-injection",)))

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_not_in_high_critical_fails_high_added():
    added = sast_finding("python.security.high", severity="high")
    policy = SecurityPolicy(
        findings=FindingsPolicy(
            added=AddedFindingsPolicy(severity=SeverityFilter(not_in=("high", "critical")))
        )
    )

    status = evaluate_security(
        policy,
        sensor_state(findings=()),
        sensor_state(findings=(added,)),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_max_count_is_global_across_sensors():
    first = sast_finding("info.rule", severity="info")
    second = sca_finding("example", severity="info")
    policy = SecurityPolicy(findings=FindingsPolicy(added=AddedFindingsPolicy(max_count=1)))

    status = evaluate_security(
        policy,
        sensor_state(
            provenances=(
                provenance(sensor_id="semgrep"),
                provenance(sensor_id="pip-audit"),
            ),
            findings=(),
        ),
        sensor_state(
            provenances=(
                provenance(sensor_id="semgrep"),
                provenance(sensor_id="pip-audit"),
            ),
            findings=(first, second),
        ),
        as_of=AS_OF,
    )

    assert status == "fail"


def test_evaluate_security_none_policy_uses_default_floor():
    high = sast_finding("bad.rule", severity="high")
    info = sast_finding("info.rule", severity="info")

    assert (
        evaluate_security(
            None,
            sensor_state(findings=()),
            sensor_state(findings=(high,)),
            as_of=AS_OF,
        )
        == "fail"
    )
    assert (
        evaluate_security(
            None,
            sensor_state(findings=()),
            sensor_state(findings=(info,)),
            as_of=AS_OF,
        )
        == "pass"
    )


def test_evaluate_security_rejects_suppression_hash_mismatch():
    added = sca_finding("django", severity="high")
    bad_suppression = Suppression(
        canonical_id=canonical_id_for_identity(
            ("v1", "sca", "pip-audit", "flask", "2.0", "PYSEC-1")
        ),
        identity_components=added.identity_components,
        reason="bad hash",
        expires=dt.date(2026, 9, 1),
        owner="security-team",
    )

    with pytest.raises(ValueError, match="suppression canonical_id"):
        evaluate_security(
            SecurityPolicy(suppressions=(bad_suppression,)),
            sensor_state(findings=()),
            sensor_state(findings=(added,)),
            as_of=AS_OF,
        )


def test_evaluate_security_scanner_policy_controls_drift_fields():
    finding = sast_finding("same.rule", severity="info")
    baseline = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:old"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(ruleset_hash="sha256:new"),),
        findings=(finding,),
    )

    default_status = evaluate_security(None, baseline, candidate, as_of=AS_OF)
    relaxed_status = evaluate_security(
        SecurityPolicy(scanner=ScannerPolicy(require_same_ruleset=False)),
        baseline,
        candidate,
        as_of=AS_OF,
    )

    assert default_status == "unknown"
    assert relaxed_status == "pass"


def test_evaluate_security_require_same_sensor_version_can_force_unknown():
    finding = sast_finding("same.rule", severity="info")
    baseline = sensor_state(
        provenances=(provenance(sensor_version="tool-1"),),
        findings=(finding,),
    )
    candidate = sensor_state(
        provenances=(provenance(sensor_version="tool-2"),),
        findings=(finding,),
    )

    status = evaluate_security(
        SecurityPolicy(scanner=ScannerPolicy(require_same_sensor_version=True)),
        baseline,
        candidate,
        as_of=AS_OF,
    )

    assert status == "unknown"


def test_evaluate_security_non_complete_sensor_contributes_unknown():
    baseline = sensor_state(
        provenances=(provenance(status="error", error_message="semgrep failed"),),
        findings=(),
    )
    candidate = sensor_state(findings=())

    assert evaluate_security(None, baseline, candidate, as_of=AS_OF) == "unknown"


def test_drift_fields_for_scanner_matches_default_and_overrides():
    assert _drift_fields_for_scanner(None) == _drift_fields_for_scanner(ScannerPolicy())
    assert _drift_fields_for_scanner(None) == frozenset(
        {
            "adapter_version",
            "identity_algorithm_version",
            "ruleset_hash",
            "advisory_db_hash",
        }
    )
    assert _drift_fields_for_scanner(
        ScannerPolicy(
            require_same_ruleset=False,
            require_same_sensor_version=True,
            require_same_advisory_db=False,
        )
    ) == frozenset(
        {
            "adapter_version",
            "identity_algorithm_version",
            "sensor_version",
        }
    )


def test_evaluate_security_is_deterministic_for_identical_inputs():
    added = sast_finding("python.security.eval", severity="high")
    policy = SecurityPolicy(suppressions=(_suppression_for(added),))
    baseline = sensor_state(findings=())
    candidate = sensor_state(findings=(added,))

    first = evaluate_security(policy, baseline, candidate, as_of=AS_OF)
    second = evaluate_security(policy, baseline, candidate, as_of=AS_OF)

    assert first == second == "pass"


def test_suite_security_layer_does_not_read_wall_clock():
    suite_root = Path("src/semantic_ci_code/suite")
    sources = {
        path.as_posix(): path.read_text(encoding="utf-8") for path in suite_root.rglob("*.py")
    }

    assert sources
    assert not any(
        needle in source
        for source in sources.values()
        for needle in ("date.today", "datetime.now", "time.time")
    )


def test_evaluate_security_uses_hand_built_json_only():
    finding = sast_finding("json.rule", severity="high")
    baseline_payload = sensor_state(findings=()).model_dump(mode="json")
    candidate_payload = sensor_state(findings=(finding,)).model_dump(mode="json")
    # JSON round-trip proves the suite evaluator does not need git, files, or scanner execution.
    baseline = SensorState.model_validate_json(json.dumps(baseline_payload))
    candidate = SensorState.model_validate_json(json.dumps(candidate_payload))

    assert evaluate_security(None, baseline, candidate, as_of=AS_OF) == "fail"
