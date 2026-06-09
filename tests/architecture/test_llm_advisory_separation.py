from __future__ import annotations

import datetime as dt

import pytest

from semantic_ci_code.evaluator import VerdictResult
from semantic_ci_code.sensor.delta import DEFAULT_DRIFT_FIELDS, compute_security_delta
from semantic_ci_code.suite.evaluator import SuiteResult, combine_verdict
from semantic_ci_code.suite.security import evaluate_security_detail
from tests.sensor.helpers import llm_finding, provenance, sast_finding, sensor_state


def test_llm_findings_are_rejected_from_verdict_delta_path():
    baseline = sensor_state(
        provenances=(
            provenance(
                sensor_id="llm-scout",
                adapter_version="llm-adapter-1",
                model_id="model-x",
                prompt_hash="sha256:prompt",
                non_reproducible=True,
            ),
        )
    )
    candidate = sensor_state(
        provenances=(
            provenance(
                sensor_id="llm-scout",
                adapter_version="llm-adapter-1",
                model_id="model-x",
                prompt_hash="sha256:prompt",
                non_reproducible=True,
            ),
        ),
        findings=(llm_finding(sensor_id="llm-scout"),),
    )

    with pytest.raises(ValueError, match="advisory-only"):
        compute_security_delta(baseline, candidate)
    with pytest.raises(ValueError, match="advisory-only"):
        evaluate_security_detail(None, baseline, candidate, as_of=dt.date(2026, 6, 9))


def test_deterministic_sast_finding_still_drives_suite_fail():
    candidate = sensor_state(findings=(sast_finding(severity="critical"),))

    delta = compute_security_delta(sensor_state(findings=()), candidate)
    suite = combine_verdict(VerdictResult.PASS, delta.aggregate_status)

    assert delta.aggregate_status == "fail"
    assert suite.final is SuiteResult.FAIL


def test_llm_provenance_fields_do_not_participate_in_drift():
    assert "model_id" not in DEFAULT_DRIFT_FIELDS
    assert "prompt_hash" not in DEFAULT_DRIFT_FIELDS
    assert "non_reproducible" not in DEFAULT_DRIFT_FIELDS

    baseline = sensor_state(
        provenances=(
            provenance(
                model_id="model-a",
                prompt_hash="sha256:prompt-a",
                non_reproducible=True,
            ),
        )
    )
    candidate = sensor_state(
        provenances=(
            provenance(
                model_id="model-b",
                prompt_hash="sha256:prompt-b",
                non_reproducible=False,
            ),
        )
    )

    delta = compute_security_delta(baseline, candidate)

    assert delta.aggregate_status == "pass"
