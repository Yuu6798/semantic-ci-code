from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from semantic_ci_code.ssp.models import (
    SASTFinding,
    SCAFinding,
    ScanEndpoint,
    SensorOutput,
    SensorSpec,
    SourceSpan,
    SSPDelta,
    SSPEngine,
    SSPEnvelope,
    SSPMetadata,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "semantic_ci_code"
    / "schemas"
    / "ssp_envelope_v1.json"
)


def test_sensor_output_error_status_rejects_findings():
    with pytest.raises(ValidationError):
        SensorOutput(
            sensor_id="semgrep",
            status="error",
            findings=(
                SASTFinding(
                    rule_id="rule",
                    module_path="src/app.py",
                    qualified_name="app",
                    normalized_text="x",
                    severity="high",
                ),
            ),
        )


def test_sensor_output_default_status_is_complete():
    assert SensorOutput(sensor_id="semgrep").status == "complete"


def test_discriminated_finding_models_dump_json():
    delta = SSPDelta(
        sensor_id="mixed",
        status="fail",
        added=(
            SASTFinding(
                rule_id="rule",
                module_path="src\\app.py",
                qualified_name="app.f",
                normalized_text="danger()",
                ordinal=0,
                fingerprint="a" * 16,
                severity="high",
                source_span=SourceSpan(start_line=1, start_col=0, end_line=1, end_col=8),
            ),
            SCAFinding(
                package_name="django",
                installed_version="3.2.0",
                advisory_id="PYSEC-1",
                fingerprint="b" * 16,
                severity="medium",
            ),
        ),
        unchanged_count=0,
    )

    data = delta.model_dump(mode="json")

    assert data["added"][0]["category"] == "sast"
    assert data["added"][0]["module_path"] == "src/app.py"
    assert data["added"][1]["category"] == "sca"


def test_envelope_json_schema_validates_conforming_payload():
    envelope = SSPEnvelope(
        engine=SSPEngine(
            scan_mode="virtual",
            baseline=ScanEndpoint(kind="virtual", ref="baseline-fixture"),
            candidate=ScanEndpoint(kind="virtual", ref="candidate-fixture"),
            sensors=(SensorSpec(id="semgrep", version="1.0", ruleset_hash="rules"),),
        ),
        deltas_by_sensor={
            "semgrep": SSPDelta(
                sensor_id="semgrep",
                status="pass",
                added=(),
                removed=(),
                unchanged_count=1,
            )
        },
        aggregate_verdict="pass",
        metadata=SSPMetadata(timestamp="2026-01-01T00:00:00Z"),
    )
    payload = envelope.model_dump(mode="json")

    assert payload["metadata"]["timestamp"] == "2026-01-01T00:00:00Z"
    assert payload["metadata"]["findings_order_invariant"] == "source-span"
    jsonschema.validate(payload, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def test_envelope_rejects_delta_map_key_sensor_id_mismatch():
    with pytest.raises(ValidationError, match="deltas_by_sensor keys must match"):
        SSPEnvelope(
            engine=SSPEngine(
                scan_mode="virtual",
                baseline=ScanEndpoint(kind="virtual", ref="baseline-fixture"),
                candidate=ScanEndpoint(kind="virtual", ref="candidate-fixture"),
                sensors=(SensorSpec(id="semgrep", version="1.0"),),
            ),
            deltas_by_sensor={
                "semgrep": SSPDelta(
                    sensor_id="pip-audit",
                    status="pass",
                    added=(),
                    removed=(),
                    unchanged_count=0,
                )
            },
            aggregate_verdict="pass",
        )


def test_envelope_rejects_aggregate_verdict_mismatch():
    with pytest.raises(ValidationError, match="aggregate_verdict must match"):
        SSPEnvelope(
            engine=SSPEngine(
                scan_mode="virtual",
                baseline=ScanEndpoint(kind="virtual", ref="baseline-fixture"),
                candidate=ScanEndpoint(kind="virtual", ref="candidate-fixture"),
                sensors=(SensorSpec(id="semgrep", version="1.0"),),
            ),
            deltas_by_sensor={
                "semgrep": SSPDelta(
                    sensor_id="semgrep",
                    status="pass",
                    added=(),
                    removed=(),
                    unchanged_count=0,
                )
            },
            aggregate_verdict="fail",
        )
