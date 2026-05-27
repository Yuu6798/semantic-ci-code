from __future__ import annotations

from semantic_ci_code.ssp.human_format import format_human
from semantic_ci_code.ssp.models import (
    SASTFinding,
    ScanEndpoint,
    SensorSpec,
    SourceSpan,
    SSPDelta,
    SSPEngine,
    SSPEnvelope,
)


def test_human_format_includes_summary_counts_and_finding_details():
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
                        rule_id="python.security.eval",
                        module_path="src/app.py",
                        qualified_name="src.app.handler",
                        normalized_text="eval(user_input)",
                        severity="high",
                        message="New eval use",
                        source_span=SourceSpan(
                            start_line=5,
                            start_col=5,
                            end_line=5,
                            end_col=21,
                        ),
                    ),
                ),
                removed=(),
                unchanged_count=1,
            )
        },
        aggregate_verdict="fail",
    )

    output = format_human(envelope)

    assert "aggregate verdict: fail" in output
    assert "sensor: semgrep" in output
    assert "added: 1" in output
    assert "unchanged: 1" in output
    assert "[high] python.security.eval at src/app.py:5 - New eval use" in output
