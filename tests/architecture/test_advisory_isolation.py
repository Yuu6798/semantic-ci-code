from __future__ import annotations

import inspect

from semantic_ci_code.sensor.advisory import (
    AdvisoryReprojection,
    compute_advisory_reprojection,
)
from semantic_ci_code.sensor.models import SecurityDelta


def test_advisory_reprojection_is_one_run_code_state_contract():
    signature = inspect.signature(compute_advisory_reprojection)

    assert tuple(signature.parameters) == ("candidate_findings", "baseline_code", "renames")
    assert "baseline_code" in signature.parameters
    assert "baseline_findings" not in signature.parameters
    assert "baseline_state" not in signature.parameters
    assert "SensorState" not in str(signature)


def test_advisory_reprojection_is_not_security_delta_type():
    assert AdvisoryReprojection is not SecurityDelta
    assert not issubclass(AdvisoryReprojection, SecurityDelta)
