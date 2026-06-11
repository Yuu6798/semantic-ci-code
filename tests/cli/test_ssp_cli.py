from __future__ import annotations

import json
from pathlib import Path

import jsonschema

import semantic_ci_code.cli.commands.ssp as ssp_command
from semantic_ci_code.ssp.adapters.pip_audit import PipAuditScanResult
from semantic_ci_code.ssp.adapters.semgrep import SemgrepScanResult
from semantic_ci_code.ssp.models import SASTFinding, SCAFinding, SensorOutput, SensorSpec

from .helpers import REPO_ROOT, parse_json, run_semantic_ci

SSP_FIXTURES = REPO_ROOT / "tests" / "ssp" / "fixtures"
BASELINE_SENSOR = SSP_FIXTURES / "semgrep_baseline_sensor.json"
CANDIDATE_SENSOR = SSP_FIXTURES / "semgrep_candidate_sensor.json"
SSP_SCHEMA = json.loads(
    (REPO_ROOT / "src" / "semantic_ci_code" / "schemas" / "ssp_envelope_v1.json").read_text(
        encoding="utf-8"
    )
)


def test_ssp_from_json_emits_schema_valid_json_envelope():
    result = run_semantic_ci(
        REPO_ROOT,
        "ssp",
        "from-json",
        "--baseline",
        str(BASELINE_SENSOR),
        "--candidate",
        str(CANDIDATE_SENSOR),
        "--format",
        "json",
    )

    assert result.returncode == 1, result.stderr
    payload = parse_json(result.stdout)
    jsonschema.validate(payload, SSP_SCHEMA)
    assert payload["schema_version"] == "ssp-1"
    assert payload["engine"]["scan_mode"] == "virtual"
    assert payload["aggregate_verdict"] == "fail"
    delta = payload["deltas_by_sensor"]["semgrep"]
    assert len(delta["added"]) == 1
    assert delta["added"][0]["rule_id"] == "python.security.eval"
    assert delta["unchanged_count"] == 1


def test_ssp_from_json_human_output_includes_counts():
    result = run_semantic_ci(
        REPO_ROOT,
        "ssp",
        "from-json",
        "--baseline",
        str(BASELINE_SENSOR),
        "--candidate",
        str(CANDIDATE_SENSOR),
        "--format",
        "human",
    )

    assert result.returncode == 1, result.stderr
    assert "aggregate verdict: fail" in result.stdout
    assert "sensor: semgrep" in result.stdout
    assert "added: 1" in result.stdout


def test_ssp_from_json_sarif_output_maps_added_finding():
    result = run_semantic_ci(
        REPO_ROOT,
        "ssp",
        "from-json",
        "--baseline",
        str(BASELINE_SENSOR),
        "--candidate",
        str(CANDIDATE_SENSOR),
        "--format",
        "sarif",
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"
    result_by_rule = {item["ruleId"]: item for item in payload["runs"][0]["results"]}
    assert result_by_rule["python.security.eval"]["level"] == "error"
    location = result_by_rule["python.security.eval"]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "src/app.py"


def test_ssp_from_json_error_sensor_returns_engine_error_with_unknown_envelope(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps(SensorOutput(sensor_id="semgrep").model_dump(mode="json")),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            SensorOutput(
                sensor_id="semgrep",
                status="error",
                error_message="semgrep missing",
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )

    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "from-json",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
    )

    assert result.returncode == 3
    payload = parse_json(result.stdout)
    assert payload["aggregate_verdict"] == "unknown"
    assert payload["deltas_by_sensor"]["semgrep"]["error_message"] == "semgrep missing"


def test_ssp_from_json_missing_file_is_usage_error(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "from-json",
        "--baseline",
        str(tmp_path / "missing.json"),
        "--candidate",
        str(CANDIDATE_SENSOR),
    )

    assert result.returncode == 2
    assert "--baseline does not exist" in result.stderr


def test_ssp_scan_semgrep_uses_adapter_and_package_root(
    monkeypatch,
    tmp_path: Path,
):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    for root in (baseline, candidate):
        (root / "src").mkdir(parents=True)
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    calls: list[tuple[Path, Path, Path]] = []

    def fake_scan(self, target_dir: Path, *, ruleset: Path, repo_root: Path) -> SemgrepScanResult:
        del self
        calls.append((target_dir, ruleset, repo_root))
        finding = ()
        if repo_root == candidate.resolve():
            finding = (
                SASTFinding(
                    rule_id="semgrep.rule",
                    module_path="src/app.py",
                    qualified_name="src.app.f",
                    normalized_text="danger()",
                    severity="high",
                    message="new",
                ),
            )
        return SemgrepScanResult(
            output=SensorOutput(sensor_id="semgrep", sensor_version="1.80.0", findings=finding),
            sensor_spec=SensorSpec(id="semgrep", version="1.80.0", ruleset_hash="sha256:test"),
        )

    monkeypatch.setattr(ssp_command.SemgrepAdapter, "scan", fake_scan)

    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "scan",
        "--sensor",
        "semgrep",
        "--config",
        str(ruleset),
        "--baseline-dir",
        str(baseline),
        "--candidate-dir",
        str(candidate),
        "--package-root",
        "src",
    )

    assert result.returncode == 1, result.stderr
    assert calls == [
        (baseline.resolve() / "src", ruleset.resolve(), baseline.resolve()),
        (candidate.resolve() / "src", ruleset.resolve(), candidate.resolve()),
    ]
    assert parse_json(result.stdout)["aggregate_verdict"] == "fail"


def test_ssp_scan_pip_audit_uses_requirements_when_present(
    monkeypatch,
    tmp_path: Path,
):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    for root in (baseline, candidate):
        root.mkdir()
        (root / "requirements.txt").write_text("django==3.2.0\n", encoding="utf-8")
    calls: list[tuple[str, Path | None, Path]] = []

    def fake_scan(self, *, source, repo_root: Path) -> PipAuditScanResult:
        del self
        calls.append((source.kind, source.path, repo_root))
        finding = ()
        if repo_root == candidate.resolve():
            finding = (
                SCAFinding(
                    package_name="django",
                    installed_version="3.2.0",
                    advisory_id="PYSEC-1",
                    severity="high",
                    message="new vuln",
                ),
            )
        return PipAuditScanResult(
            output=SensorOutput(sensor_id="pip-audit", sensor_version="2.9.0", findings=finding),
            sensor_spec=SensorSpec(id="pip-audit", version="2.9.0", advisory_db_hash=None),
        )

    monkeypatch.setattr(ssp_command.PipAuditAdapter, "scan", fake_scan)

    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "scan",
        "--sensor",
        "pip-audit",
        "--baseline-dir",
        str(baseline),
        "--candidate-dir",
        str(candidate),
    )

    assert result.returncode == 1, result.stderr
    assert calls == [
        ("requirements", baseline.resolve() / "requirements.txt", baseline.resolve()),
        ("requirements", candidate.resolve() / "requirements.txt", candidate.resolve()),
    ]
    payload = parse_json(result.stdout)
    assert payload["deltas_by_sensor"]["pip-audit"]["added"][0]["advisory_id"] == "PYSEC-1"


def test_ssp_scan_pip_audit_discovers_pdm_lock_source(
    monkeypatch,
    tmp_path: Path,
):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    for root in (baseline, candidate):
        root.mkdir()
        (root / "pdm.lock").write_text(
            """
[[package]]
name = "django"
version = "3.2.0"
""".lstrip(),
            encoding="utf-8",
        )
    calls: list[tuple[str, Path | None, Path]] = []

    def fake_scan(self, *, source, repo_root: Path) -> PipAuditScanResult:
        del self
        calls.append((source.kind, source.path, repo_root))
        finding = ()
        if repo_root == candidate.resolve():
            finding = (
                SCAFinding(
                    package_name="django",
                    installed_version="3.2.0",
                    advisory_id="PYSEC-1",
                    severity="high",
                    message="new vuln",
                ),
            )
        return PipAuditScanResult(
            output=SensorOutput(sensor_id="pip-audit", sensor_version="2.9.0", findings=finding),
            sensor_spec=SensorSpec(id="pip-audit", version="2.9.0", advisory_db_hash=None),
        )

    monkeypatch.setattr(ssp_command.PipAuditAdapter, "scan", fake_scan)

    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "scan",
        "--sensor",
        "pip-audit",
        "--baseline-dir",
        str(baseline),
        "--candidate-dir",
        str(candidate),
    )

    assert result.returncode == 1, result.stderr
    assert calls == [
        ("pdm-lock", baseline.resolve() / "pdm.lock", baseline.resolve()),
        ("pdm-lock", candidate.resolve() / "pdm.lock", candidate.resolve()),
    ]
    payload = parse_json(result.stdout)
    assert payload["aggregate_verdict"] == "fail"


def test_ssp_scan_pip_audit_fallback_unknown_exit_is_preserved(
    monkeypatch,
    tmp_path: Path,
):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()

    def fake_scan(self, *, source, repo_root: Path) -> PipAuditScanResult:
        del self, repo_root
        assert source.kind == "fallback"
        return PipAuditScanResult(
            output=SensorOutput(
                sensor_id="pip-audit",
                sensor_version="2.9.0",
                status="error",
                findings=(),
                error_message="no recognized dependency source",
            ),
            sensor_spec=SensorSpec(id="pip-audit", version="2.9.0", advisory_db_hash=None),
        )

    monkeypatch.setattr(ssp_command.PipAuditAdapter, "scan", fake_scan)

    result = run_semantic_ci(
        tmp_path,
        "ssp",
        "scan",
        "--sensor",
        "pip-audit",
        "--baseline-dir",
        str(baseline),
        "--candidate-dir",
        str(candidate),
    )

    assert result.returncode == 3
    payload = parse_json(result.stdout)
    assert payload["aggregate_verdict"] == "unknown"
