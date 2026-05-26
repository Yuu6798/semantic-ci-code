from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from semantic_ci_code.ssp.delta import compute_delta
from semantic_ci_code.ssp.models import SASTFinding, SensorOutput, SourceSpan

REPO_ROOT = Path(__file__).resolve().parents[2]


def _finding(rule_id: str, line: int) -> SASTFinding:
    return SASTFinding(
        rule_id=rule_id,
        module_path="src/app.py",
        qualified_name="app.handler",
        normalized_text="danger()",
        source_span=SourceSpan(start_line=line, start_col=0, end_line=line, end_col=8),
        severity="high",
    )


def _frozen_delta_bytes() -> bytes:
    delta = compute_delta(
        SensorOutput(sensor_id="semgrep", findings=(_finding("old", 1),)),
        SensorOutput(sensor_id="semgrep", findings=(_finding("old", 1), _finding("new", 2))),
    )
    payload = delta.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_frozen_fixture_is_byte_identical_across_runs():
    assert _frozen_delta_bytes() == _frozen_delta_bytes()


def test_delta_is_byte_identical_across_pythonhashseed_values():
    script = textwrap.dedent(
        """
        import json

        from semantic_ci_code.ssp.delta import compute_delta
        from semantic_ci_code.ssp.models import SASTFinding, SensorOutput, SourceSpan


        def f(rule, line):
            return SASTFinding(
                rule_id=rule,
                module_path="src/app.py",
                qualified_name="app.handler",
                normalized_text="danger()",
                source_span=SourceSpan(
                    start_line=line,
                    start_col=0,
                    end_line=line,
                    end_col=8,
                ),
                severity="high",
            )


        delta = compute_delta(
            SensorOutput(sensor_id="semgrep", findings=(f("old", 1),)),
            SensorOutput(sensor_id="semgrep", findings=(f("old", 1), f("new", 2))),
        )
        print(json.dumps(delta.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))
        """
    )
    outputs = []
    for seed in ("0", "1", "random"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "PYTHONHASHSEED": seed},
            text=True,
            capture_output=True,
            check=True,
        )
        outputs.append(result.stdout)

    assert outputs[0] == outputs[1] == outputs[2]
