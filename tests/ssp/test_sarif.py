from __future__ import annotations

import json

from semantic_ci_code.ssp.models import (
    SASTFinding,
    SCAFinding,
    ScanEndpoint,
    SensorSpec,
    SourceSpan,
    SSPDelta,
    SSPEngine,
    SSPEnvelope,
)
from semantic_ci_code.ssp.sarif import ssp_to_sarif


def test_ssp_to_sarif_maps_levels_rules_and_locations():
    envelope = SSPEnvelope(
        engine=SSPEngine(
            scan_mode="virtual",
            baseline=ScanEndpoint(kind="prebuilt", ref="baseline.json"),
            candidate=ScanEndpoint(kind="prebuilt", ref="candidate.json"),
            sensors=(SensorSpec(id="semgrep", version="1.80.0"),),
        ),
        deltas_by_sensor={
            "semgrep": SSPDelta(
                sensor_id="semgrep",
                status="fail",
                added=(
                    SASTFinding(
                        rule_id="critical.rule",
                        module_path="src/app.py",
                        qualified_name="src.app.handler",
                        normalized_text="danger()",
                        severity="critical",
                        message="critical",
                        source_span=SourceSpan(
                            start_line=5,
                            start_col=1,
                            end_line=5,
                            end_col=9,
                        ),
                    ),
                    SASTFinding(
                        rule_id="medium.rule",
                        module_path="src/app.py",
                        qualified_name="src.app.handler",
                        normalized_text="warn()",
                        severity="medium",
                        message="medium",
                        source_span=SourceSpan(
                            start_line=8,
                            start_col=1,
                            end_line=8,
                            end_col=7,
                        ),
                    ),
                    SCAFinding(
                        package_name="django",
                        installed_version="3.2.0",
                        advisory_id="PYSEC-1",
                        severity="low",
                        message="low advisory",
                    ),
                ),
                removed=(),
                unchanged_count=0,
            )
        },
        aggregate_verdict="fail",
    )

    sarif = json.loads(ssp_to_sarif(envelope))
    results = {result["ruleId"]: result for result in sarif["runs"][0]["results"]}

    assert sarif["version"] == "2.1.0"
    assert results["critical.rule"]["level"] == "error"
    assert results["medium.rule"]["level"] == "warning"
    assert results["PYSEC-1"]["level"] == "note"
    location = results["critical.rule"]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "src/app.py"
    assert location["region"]["startLine"] == 5
