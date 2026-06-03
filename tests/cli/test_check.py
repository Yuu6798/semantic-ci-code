from __future__ import annotations

import datetime as dt
import json
import pickle
import time
from pathlib import Path

import pytest

import semantic_ci_code.pipeline.python_code_state as code_state_pipeline
from semantic_ci_code.cli.git_runtime import GitCommandError
from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    SCASecurityFinding,
    SensorProvenance,
    SensorState,
    SourceSpan,
    canonical_id_for_identity,
)

from .git_helpers import (
    BAD_SOURCE,
    BASELINE_SOURCE,
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    TARGET_PASS,
    git,
    init_repo,
    init_repo_without_candidate_commit,
    init_topic_only_repo,
    run,
    stage_changes,
    write_file,
)
from .helpers import REPO_ROOT, parse_json, payload, run_semantic_ci, run_semantic_ci_subprocess

COMPARE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
COMPARE_BASELINE = COMPARE_FIXTURES / "baseline_pkg"
COMPARE_CANDIDATE = COMPARE_FIXTURES / "candidate_pkg"
COMPARE_PASS_TARGET = COMPARE_FIXTURES / "target_pass.yaml"
COMPARE_REPAIR_TARGET = COMPARE_FIXTURES / "target_repair.yaml"
COMPARE_FAIL_TARGET = COMPARE_FIXTURES / "target_fail.yaml"
COMPARE_INVALID_TARGET = COMPARE_FIXTURES / "target_invalid.yaml"
TARGET_NO_USER_CONSTRAINTS = (
    "intent: no user constraints\nchange:\n  primary_kind: feature\nconstraints: []\n"
)
TARGET_COMPLEXITY_TIMEOUT = """\
intent: tolerate slow complexity extractor
change:
  primary_kind: feature
constraints:
  - id: complexity_timeout
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than
    expected: 1
    severity: soft
    unknown_policy: repair
"""
TARGET_SECURITY_DENY_ADDED = """\
intent: add a public API with security policy
change:
  primary_kind: feature
security:
  rules:
    deny_added:
      - python.security.denied
constraints:
  - id: added_api_present
    kind: delta
    target: api_surface_delta.added
    operator: includes_any
    expected:
      - fqn: mod.added
        kind: function
        visibility: public
"""


def compare_args(target: Path = COMPARE_PASS_TARGET) -> list[str]:
    return [
        "compare",
        "--baseline-dir",
        str(COMPARE_BASELINE),
        "--candidate-dir",
        str(COMPARE_CANDIDATE),
        "--target",
        str(target),
    ]


def test_check_pass_fixture_exits_zero_with_json_verdict_pass(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_PASS_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_check_repair_fixture_exits_zero_by_default(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_REPAIR_TARGET), "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "repair"


def test_check_repair_fixture_strict_repair_exits_one(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(
        REPO_ROOT,
        *compare_args(COMPARE_REPAIR_TARGET),
        "--format",
        "json",
        "--strict-repair",
    )

    assert result.returncode == 1
    assert payload(result)["verdict"] == "repair"


def test_check_fail_fixture_exits_one(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_FAIL_TARGET), "--format", "json")

    assert result.returncode == 1
    assert payload(result)["verdict"] == "fail"


def test_origin_main_ref_is_used_when_present(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_check_without_sensor_flags_keeps_code_only_payload(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    data = payload(result)
    assert data["verdict"] == "pass"
    assert "security" not in data
    assert "suite_verdict" not in data


def test_check_sensor_security_fail_changes_exit_and_payload(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(_sast_finding("python.security.eval", severity="high"),),
    )

    result = _run_check_with_sensors(repo, sensor_baseline, sensor_candidate)

    assert result.returncode == 1
    data = payload(result)
    assert data["verdict"] == "pass"
    assert data["security"]["verdict"] == "fail"
    assert data["security"]["as_of"] == "2026-09-01"
    assert data["security"]["global_count_violated"] is False
    sensor = data["security"]["sensors"][0]
    assert sensor["sensor_id"] == "semgrep"
    assert sensor["status"] == "fail"
    assert sensor["added"][0]["rule_id"] == "python.security.eval"
    assert sensor["removed"] == []
    assert sensor["suppressed"] == []
    assert sensor["drift_reason"] is None
    assert sensor["unchanged_count"] == 0
    assert data["suite_verdict"] == "fail"


def test_check_sensor_security_pass_preserves_code_exit(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(_sast_finding("python.security.info", severity="info"),),
    )

    result = _run_check_with_sensors(repo, sensor_baseline, sensor_candidate)

    assert result.returncode == 0
    data = payload(result)
    assert data["verdict"] == "pass"
    assert data["security"]["verdict"] == "pass"
    assert data["security"]["as_of"] == "2026-09-01"
    sensor = data["security"]["sensors"][0]
    assert sensor["status"] == "pass"
    assert sensor["added"][0]["severity"] == "info"
    assert data["suite_verdict"] == "pass"


def test_check_sensor_json_includes_removed_security_detail(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    removed = _sast_finding("python.security.removed", severity="high")
    sensor_baseline = _write_sensor_state(
        tmp_path / "sensor-baseline.json",
        findings=(removed,),
    )
    sensor_candidate = _write_sensor_state(tmp_path / "sensor-candidate.json")

    result = _run_check_with_sensors(repo, sensor_baseline, sensor_candidate)

    assert result.returncode == 0
    sensor = payload(result)["security"]["sensors"][0]
    assert sensor["status"] == "pass"
    assert sensor["added"] == []
    assert sensor["removed"][0]["canonical_id"] == removed.canonical_id
    assert sensor["suppressed"] == []


def test_check_sensor_unknown_returns_engine_error_exit(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(
        tmp_path / "sensor-baseline.json",
        provenances=(_provenance(ruleset_hash="sha256:old"),),
    )
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        provenances=(_provenance(ruleset_hash="sha256:new"),),
    )

    result = _run_check_with_sensors(repo, sensor_baseline, sensor_candidate)

    assert result.returncode == 3
    data = payload(result)
    assert data["verdict"] == "pass"
    assert data["security"]["verdict"] == "unknown"
    assert data["security"]["as_of"] == "2026-09-01"
    sensor = data["security"]["sensors"][0]
    assert sensor["status"] == "unknown"
    assert sensor["added"] == []
    assert sensor["removed"] == []
    assert sensor["suppressed"] == []
    assert "ruleset_hash" in sensor["drift_reason"]
    assert data["suite_verdict"] == "unknown"


def test_check_sensor_flags_must_be_provided_together(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(
        repo,
        "check",
        "--sensor-baseline",
        str(tmp_path / "sensor-baseline.json"),
    )

    assert result.returncode == 2
    assert "--sensor-baseline and --sensor-candidate must be provided together" in result.stderr


def test_check_sensor_state_invalid_json_is_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    bad_sensor = tmp_path / "bad.json"
    bad_sensor.write_text("{not-json", encoding="utf-8")
    sensor_candidate = _write_sensor_state(tmp_path / "sensor-candidate.json")

    result = _run_check_with_sensors(repo, bad_sensor, sensor_candidate)

    assert result.returncode == 2
    assert "--sensor-baseline must be a valid SensorState JSON file" in result.stderr


def test_check_as_of_rejects_invalid_date(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(tmp_path / "sensor-candidate.json")

    result = run_semantic_ci(
        repo,
        "check",
        "--sensor-baseline",
        str(sensor_baseline),
        "--sensor-candidate",
        str(sensor_candidate),
        "--as-of",
        "not-a-date",
    )

    assert result.returncode == 2
    assert "--as-of must be a valid YYYY-MM-DD date" in result.stderr


def test_check_as_of_rejects_invalid_date_without_sensor_flags(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)

    result = run_semantic_ci(repo, "check", "--as-of", "not-a-date")

    assert result.returncode == 2
    assert "--as-of must be a valid YYYY-MM-DD date" in result.stderr


def test_check_target_security_policy_can_fail_info_finding_by_rule(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    write_file(repo / "target.yaml", TARGET_SECURITY_DENY_ADDED)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(_sast_finding("python.security.denied", severity="info"),),
    )

    result = _run_check_with_sensors(repo, sensor_baseline, sensor_candidate)

    assert result.returncode == 1
    data = payload(result)
    assert data["verdict"] == "pass"
    assert data["security"]["verdict"] == "fail"
    assert data["suite_verdict"] == "fail"


def test_check_as_of_controls_security_suppression_expiry(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    finding = _sast_finding("python.security.suppressed", severity="high")
    write_file(repo / "target.yaml", _target_with_suppression(finding, expires=dt.date(2026, 9, 1)))
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(finding,),
    )

    active = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        as_of="2026-09-01",
    )
    expired = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        as_of="2026-09-02",
    )

    assert active.returncode == 0
    active_payload = payload(active)
    assert active_payload["security"]["verdict"] == "pass"
    assert active_payload["security"]["sensors"][0]["added"] == []
    assert active_payload["security"]["sensors"][0]["suppressed"][0]["canonical_id"] == (
        finding.canonical_id
    )
    assert active_payload["suite_verdict"] == "pass"
    assert expired.returncode == 1
    expired_payload = payload(expired)
    assert expired_payload["security"]["verdict"] == "fail"
    assert expired_payload["security"]["sensors"][0]["added"][0]["canonical_id"] == (
        finding.canonical_id
    )
    assert expired_payload["security"]["sensors"][0]["suppressed"] == []
    assert expired_payload["suite_verdict"] == "fail"


def test_check_human_output_includes_security_and_suite_verdicts(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(tmp_path / "sensor-candidate.json")

    result = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="human",
    )

    text = result.stdout
    assert result.returncode == 0
    assert "Security verdict: PASS  (as_of=2026-09-01)" in text
    assert "Suite final: PASS" in text
    assert "[semgrep] PASS  added=0 removed=0 suppressed=0 unchanged=0" in text


def test_check_human_output_lists_added_security_findings(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    finding = _sast_finding(
        "python.security.eval",
        severity="high",
        source_span=SourceSpan(start_line=7, end_line=7, start_col=1, end_col=17),
    )
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(finding,),
    )

    result = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="human",
    )

    assert result.returncode == 1
    assert "[semgrep] FAIL  added=1 removed=0 suppressed=0 unchanged=0" in result.stdout
    assert "+ python.security.eval [high] at src/app.py:7 - finding" in result.stdout


def test_check_human_output_includes_suppressed_count_and_drift_reason(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    finding = _sast_finding("python.security.suppressed", severity="high")
    write_file(repo / "target.yaml", _target_with_suppression(finding, expires=dt.date(2026, 9, 1)))
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(finding,),
    )

    suppressed = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="human",
    )

    assert suppressed.returncode == 0
    assert "[semgrep] PASS  added=0 removed=0 suppressed=1 unchanged=0" in suppressed.stdout
    assert "suppressed: 1" in suppressed.stdout

    drift_baseline = _write_sensor_state(
        tmp_path / "sensor-drift-baseline.json",
        provenances=(_provenance(ruleset_hash="sha256:old"),),
    )
    drift_candidate = _write_sensor_state(
        tmp_path / "sensor-drift-candidate.json",
        provenances=(_provenance(ruleset_hash="sha256:new"),),
    )
    drift = _run_check_with_sensors(
        repo,
        drift_baseline,
        drift_candidate,
        output_format="human",
    )

    assert drift.returncode == 3
    assert "[semgrep] UNKNOWN  added=0 removed=0 suppressed=0 unchanged=0" in drift.stdout
    assert "drift: " in drift.stdout
    assert "ruleset_hash" in drift.stdout


def test_check_sensor_ingest_does_not_execute_live_security_scanners():
    check_source = (
        REPO_ROOT / "src" / "semantic_ci_code" / "cli" / "commands" / "check.py"
    ).read_text(encoding="utf-8")

    assert "subprocess" not in check_source
    assert ".scan(" not in check_source


@pytest.mark.parametrize("output_format", ["gh-actions"])
def test_check_sensor_flags_reject_code_only_formats(tmp_path: Path, output_format: str):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        findings=(_sast_finding("python.security.eval", severity="high"),),
    )

    result = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format=output_format,
    )

    assert result.returncode == 2
    assert "sensor-enabled check supports json, human, or sarif output" in result.stderr
    assert result.stdout == ""


def test_check_sarif_output_merges_security_results_into_same_run(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    high = _sast_finding(
        "python.security.high",
        severity="high",
        source_span=SourceSpan(start_line=7, end_line=7, start_col=1, end_col=17),
    )
    info = _sast_finding("python.security.info", severity="info", ordinal=1)
    medium = _sca_finding("PYSEC-2026-1", severity="medium")
    provenances = (
        _provenance(sensor_id="semgrep"),
        _provenance(
            sensor_id="pip-audit",
            ruleset_hash=None,
            advisory_db_hash="sha256:advisory-db",
        ),
    )
    sensor_baseline = _write_sensor_state(
        tmp_path / "sensor-baseline.json",
        provenances=provenances,
    )
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        provenances=provenances,
        findings=(high, info, medium),
    )

    first = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="sarif",
    )
    second = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="sarif",
    )

    assert first.returncode == 1
    assert first.stdout == second.stdout
    document = json.loads(first.stdout)
    run = document["runs"][0]
    results = {item["ruleId"]: item for item in run["results"]}
    rule_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}

    assert "security/python.security.high" in rule_ids
    assert "security/python.security.info" in rule_ids
    assert "security/PYSEC-2026-1" in rule_ids
    assert results["security/python.security.high"]["level"] == "error"
    assert results["security/python.security.info"]["level"] == "note"
    assert results["security/PYSEC-2026-1"]["level"] == "warning"
    assert results["security/python.security.high"]["properties"] == {
        "category": "sast",
        "sensor_id": "semgrep",
        "severity": "high",
        "canonical_id": high.canonical_id,
    }
    high_location = results["security/python.security.high"]["locations"][0]
    assert high_location["physicalLocation"]["artifactLocation"]["uri"] == "src/app.py"
    assert high_location["physicalLocation"]["region"] == {
        "startLine": 7,
        "endLine": 7,
        "startColumn": 1,
        "endColumn": 17,
    }
    assert "locations" not in results["security/PYSEC-2026-1"]


def test_check_sarif_output_emits_drift_note_for_unknown_sensor(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=True)
    sensor_baseline = _write_sensor_state(
        tmp_path / "sensor-baseline.json",
        provenances=(_provenance(ruleset_hash="sha256:old"),),
    )
    sensor_candidate = _write_sensor_state(
        tmp_path / "sensor-candidate.json",
        provenances=(_provenance(ruleset_hash="sha256:new"),),
    )

    result = _run_check_with_sensors(
        repo,
        sensor_baseline,
        sensor_candidate,
        output_format="sarif",
    )

    assert result.returncode == 3
    document = json.loads(result.stdout)
    drift = next(
        item
        for item in document["runs"][0]["results"]
        if item["ruleId"] == "security/provenance-drift"
    )
    assert drift["level"] == "note"
    assert drift["properties"]["sensor_id"] == "semgrep"
    assert "ruleset_hash" in drift["message"]["text"]


def test_check_extractor_timeout_surfaces_extraction_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_COMPLEXITY_TIMEOUT)

    def slow_complexity(*args, **kwargs):
        del args, kwargs
        time.sleep(1.0)
        return ()

    monkeypatch.setattr(
        code_state_pipeline,
        "extract_python_complexity_from_paths",
        slow_complexity,
    )

    result = run_semantic_ci(
        repo,
        "check",
        "--no-fetch",
        "--no-cache",
        "--extractor-timeout",
        "0.2",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    data = payload(result)
    timeout_result = next(
        item for item in data["results"] if item["constraint_id"] == "complexity_timeout"
    )
    assert data["verdict"] == "repair"
    assert data["engine"]["timed_out_dimensions"] == ["complexity"]
    assert timeout_result["status"] == "unknown"
    assert timeout_result["unknown_cause"] == "extraction"
    assert timeout_result["error_code"] == "E_DIMENSION_TIMED_OUT"
    timeout_instruction = next(
        item
        for item in data["repair_plan"]["instructions"]
        if item["constraint_id"] == "complexity_timeout"
    )
    assert timeout_instruction["repair_code"] == "R_EXTRACTION_TIMEOUT"


@pytest.mark.parametrize("timeout", ["nan", "inf", "-inf", "0"])
def test_check_rejects_non_finite_or_non_positive_extractor_timeout(
    tmp_path: Path,
    timeout: str,
):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--no-fetch",
        "--mode",
        "smoke",
        f"--extractor-timeout={timeout}",
        "--format",
        "json",
    )

    assert result.returncode == 2
    assert "--extractor-timeout must be a finite value greater than 0 seconds" in result.stderr


def test_main_fallback_is_used_when_origin_main_is_missing(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=False)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_baseline_candidates_exit_engine_error(tmp_path: Path):
    repo = init_topic_only_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
    )

    assert result.returncode == 3
    assert "origin/main, main, master" in result.stderr


def test_explicit_baseline_rev_runs_against_given_sha(tmp_path: Path):
    repo = init_repo(tmp_path)
    baseline_sha = git(repo, "rev-parse", "main").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--baseline-rev",
        baseline_sha,
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_no_fetch_skips_fetch_commands(tmp_path: Path):
    repo = init_repo(tmp_path, origin_ref=False)
    command_log = tmp_path / "git-commands.jsonl"

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--no-fetch",
        extra_env={"SEMANTIC_CI_GIT_COMMAND_LOG": str(command_log)},
    )

    assert result.returncode == 0
    records = [
        parse_json(line)["args"] for line in command_log.read_text(encoding="utf-8").splitlines()
    ]
    assert not any(command[1] == "fetch" for command in records)


def test_candidate_source_working_tree_uses_working_directory_as_candidate(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
        "--candidate-source",
        "working-tree",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_default_candidate_source_commit_uses_head_without_dirty_warning(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 1
    assert "working tree is dirty" not in result.stderr
    assert payload(result)["verdict"] == "fail"


@pytest.mark.parametrize(
    ("side", "source", "rev_flag", "expected_message"),
    (
        (
            "candidate",
            "working-tree",
            "--candidate-rev",
            "error: --candidate-source=working-tree is incompatible with --candidate-rev",
        ),
        (
            "candidate",
            "staged-index",
            "--candidate-rev",
            "error: --candidate-source=staged-index is incompatible with --candidate-rev",
        ),
        (
            "baseline",
            "working-tree",
            "--baseline-rev",
            "error: --baseline-source=working-tree is incompatible with --baseline-rev",
        ),
        (
            "baseline",
            "staged-index",
            "--baseline-rev",
            "error: --baseline-source=staged-index is incompatible with --baseline-rev",
        ),
    ),
)
def test_volatile_source_conflicts_with_explicit_rev(
    tmp_path: Path,
    side: str,
    source: str,
    rev_flag: str,
    expected_message: str,
):
    repo = init_repo(tmp_path)
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        f"--{side}-source",
        source,
        rev_flag,
        sha,
        "--format",
        "json",
    )

    assert result.returncode == 2
    assert result.stderr == f"{expected_message}\n"


@pytest.mark.parametrize("source", ("working-tree", "staged-index"))
def test_same_volatile_source_warns_and_runs(tmp_path: Path, source: str):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "target.yaml", TARGET_NO_USER_CONSTRAINTS)

    result = run_semantic_ci(
        repo,
        "--verbose",
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--baseline-source",
        source,
        "--candidate-source",
        source,
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert (
        "warning: baseline and candidate resolve to the same "
        f"{source} snapshot; verdict will report no drift by construction."
    ) in result.stderr
    assert payload(result)["engine"]["baseline"] == {"source": source, "rev": None}
    assert payload(result)["engine"]["candidate"] == {"source": source, "rev": None}


def test_candidate_source_working_tree_clean_verbose_note(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "--verbose",
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--candidate-source",
        "working-tree",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert (
        "note: candidate source = working tree (no uncommitted changes detected; "
        "equivalent to HEAD)."
    ) in result.stderr


def test_check_json_provenance_for_commit_and_working_tree_sources(tmp_path: Path):
    repo = init_repo(tmp_path / "commit-default")
    baseline_sha = git(repo, "rev-parse", "origin/main").stdout.strip()
    candidate_sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    default_commit = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )
    assert list(default_commit["engine"]) == [
        "baseline",
        "candidate",
        "extractor_pyver",
        "package_version",
    ]
    assert default_commit["engine"]["baseline"] == {
        "source": "commit",
        "rev": baseline_sha,
    }
    assert default_commit["engine"]["candidate"] == {
        "source": "commit",
        "rev": candidate_sha,
    }

    working_tree_repo = init_repo_without_candidate_commit(tmp_path / "working-tree")
    write_file(working_tree_repo / "mod.py", CANDIDATE_SOURCE)
    working_tree_baseline_sha = git(working_tree_repo, "rev-parse", "origin/main").stdout.strip()
    working_tree = payload(
        run_semantic_ci(
            working_tree_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-source",
            "working-tree",
            "--format",
            "json",
        )
    )
    assert working_tree["engine"]["baseline"] == {
        "source": "commit",
        "rev": working_tree_baseline_sha,
    }
    assert working_tree["engine"]["candidate"] == {
        "source": "working-tree",
        "rev": None,
    }

    staged_repo = init_repo_without_candidate_commit(tmp_path / "staged-candidate")
    stage_changes(staged_repo, {"mod.py": CANDIDATE_SOURCE})
    staged_baseline_sha = git(staged_repo, "rev-parse", "HEAD").stdout.strip()
    staged = payload(
        run_semantic_ci(
            staged_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-source",
            "staged-index",
            "--format",
            "json",
        )
    )
    assert staged["engine"]["baseline"] == {
        "source": "commit",
        "rev": staged_baseline_sha,
    }
    assert staged["engine"]["candidate"] == {
        "source": "staged-index",
        "rev": None,
    }
    assert staged["verdict"] == "pass"

    staged_baseline_repo = init_repo(tmp_path / "staged-baseline")
    staged_baseline_candidate_sha = git(staged_baseline_repo, "rev-parse", "HEAD").stdout.strip()
    staged_baseline = payload(
        run_semantic_ci(
            staged_baseline_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--baseline-source",
            "staged-index",
            "--format",
            "json",
        )
    )
    assert staged_baseline["engine"]["baseline"] == {
        "source": "staged-index",
        "rev": None,
    }
    assert staged_baseline["engine"]["candidate"] == {
        "source": "commit",
        "rev": staged_baseline_candidate_sha,
    }

    explicit_repo = init_repo(tmp_path / "explicit-ref")
    explicit_baseline_sha = git(explicit_repo, "rev-parse", "origin/main").stdout.strip()
    explicit_candidate_sha = git(explicit_repo, "rev-parse", "HEAD").stdout.strip()
    explicit = payload(
        run_semantic_ci(
            explicit_repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--candidate-rev",
            explicit_candidate_sha,
            "--format",
            "json",
        )
    )
    assert explicit["engine"]["baseline"] == {
        "source": "commit",
        "rev": explicit_baseline_sha,
    }
    assert explicit["engine"]["candidate"] == {
        "source": "commit",
        "rev": explicit_candidate_sha,
    }


def test_candidate_source_staged_index_defaults_baseline_to_head(tmp_path: Path):
    repo = init_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--candidate-source",
        "staged-index",
        "--format",
        "json",
    )

    data = payload(result)
    assert result.returncode == 1
    assert data["engine"]["baseline"] == {"source": "commit", "rev": head}
    assert data["engine"]["candidate"] == {"source": "staged-index", "rev": None}


def test_worktree_cleanup_on_success(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    worktrees = git(repo, "worktree", "list", "--porcelain").stdout
    assert "semantic-ci-baseline-" not in worktrees
    assert "semantic-ci-candidate-" not in worktrees


def test_worktree_cleanup_after_extraction_error(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "mod.py", BAD_SOURCE)
    git(repo, "add", "mod.py")
    git(repo, "commit", "-m", "bad candidate")

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 3
    assert "extractor failed:" in result.stderr
    worktrees = git(repo, "worktree", "list", "--porcelain").stdout
    assert "semantic-ci-baseline-" not in worktrees
    assert "semantic-ci-candidate-" not in worktrees


def test_git_not_found_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--format",
        "json",
        extra_env={"PATH": str(tmp_path / "empty-path")},
    )

    assert result.returncode == 3
    assert "git is required for 'check'; install git or use 'compare'" in result.stderr


def test_shallow_clone_fetch_fallback_resolves_origin_main(tmp_path: Path):
    source = init_repo(tmp_path / "source")
    bare = tmp_path / "remote.git"
    clone = tmp_path / "shallow"
    run(["git", "clone", "--bare", str(source), str(bare)], cwd=tmp_path)
    run(
        [
            "git",
            "clone",
            "--depth=1",
            "--branch",
            "feature",
            bare.as_uri(),
            str(clone),
        ],
        cwd=tmp_path,
    )

    result = run_semantic_ci(clone, "check", "--mode", "smoke", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_files_touched_and_loc_delta_are_zero_for_identical_refs(tmp_path: Path):
    repo = init_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    write_file(repo / "target.yaml", "intent: same ref\nchange:\n  primary_kind: feature\n")

    data = payload(
        run_semantic_ci(
            repo,
            "check",
            "--mode",
            "smoke",
            "--no-fetch",
            "--baseline-rev",
            head,
            "--candidate-rev",
            head,
            "--format",
            "json",
        )
    )

    assert data["files_touched"] == 0
    assert data["loc_delta"] == {"added": 0, "removed": 0}


def test_files_touched_is_populated_for_different_refs(tmp_path: Path):
    repo = init_repo(tmp_path)

    data = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )

    assert data["files_touched"] > 0


def test_loc_delta_matches_git_numstat_for_different_refs(tmp_path: Path):
    repo = init_repo(tmp_path)

    data = payload(
        run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")
    )

    assert data["loc_delta"] == {"added": 4, "removed": 0}


def test_target_yaml_is_loaded_from_invoking_cwd_not_worktree(tmp_path: Path):
    repo = init_repo(tmp_path)
    git(repo, "switch", "main")
    write_file(repo / "target.yaml", TARGET_FAIL)
    git(repo, "add", "target.yaml")
    git(repo, "commit", "-m", "commit failing target")
    git(repo, "switch", "feature")
    write_file(repo / "target.yaml", TARGET_PASS)

    result = run_semantic_ci(repo, "check", "--mode", "smoke", "--no-fetch", "--format", "json")

    assert result.returncode == 0
    assert payload(result)["intent"] == "add a public API"


def test_invalid_explicit_baseline_ref_exits_engine_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--baseline-rev",
        "not-a-ref",
        "--format",
        "json",
    )

    assert result.returncode == 3
    assert "not-a-ref" in result.stderr


def test_subprocess_determinism_across_hash_seeds(tmp_path: Path):
    repo = init_repo(tmp_path)

    first = run_semantic_ci_subprocess(
        repo,
        "check",
        "--format",
        "json",
        "--no-cache",
        hash_seed="1",
    )
    second = run_semantic_ci_subprocess(
        repo,
        "check",
        "--format",
        "json",
        "--no-cache",
        hash_seed="2",
    )

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_invalid_target_yaml_exits_engine_error(tmp_path: Path):
    del tmp_path
    result = run_semantic_ci(REPO_ROOT, *compare_args(COMPARE_INVALID_TARGET), "--format", "json")

    assert result.returncode == 3
    assert "constraints[0].operator" in result.stderr


def test_package_root_relative_path_is_applied_inside_each_worktree(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "pkg" / "mod.py", BASELINE_SOURCE)
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    baseline_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    git(repo, "switch", "-c", "feature")
    write_file(repo / "pkg" / "mod.py", CANDIDATE_SOURCE)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "candidate")

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--package-root",
        "pkg",
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert payload(result)["verdict"] == "pass"


def test_missing_package_root_exits_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--package-root",
        "missing",
        "--format",
        "json",
    )

    assert result.returncode == 2
    assert "baseline package_root does not exist" in result.stderr


def test_git_command_error_is_pickle_compatible(tmp_path: Path):
    err = GitCommandError(
        ["rev-parse", "missing"],
        cwd=tmp_path,
        returncode=1,
        stderr="bad ref",
    )

    restored = pickle.loads(pickle.dumps(err))

    assert str(restored) == str(err)


def _run_check_with_sensors(
    repo: Path,
    sensor_baseline: Path,
    sensor_candidate: Path,
    *,
    as_of: str = "2026-09-01",
    output_format: str = "json",
):
    return run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        output_format,
        "--sensor-baseline",
        str(sensor_baseline),
        "--sensor-candidate",
        str(sensor_candidate),
        "--as-of",
        as_of,
    )


def _write_sensor_state(
    path: Path,
    *,
    provenances: tuple[SensorProvenance, ...] | None = None,
    findings: tuple[SASTSecurityFinding | SCASecurityFinding, ...] = (),
) -> Path:
    if provenances is None:
        sensor_ids = sorted({finding.sensor_id for finding in findings} or {"semgrep"})
        provenances = tuple(_provenance(sensor_id=sensor_id) for sensor_id in sensor_ids)
    state = SensorState(
        provenance_by_sensor={item.sensor_id: item for item in provenances},
        findings=tuple(sorted(findings, key=lambda finding: finding.canonical_id)),
    )
    path.write_text(state.model_dump_json(), encoding="utf-8")
    return path


def _provenance(
    sensor_id: str = "semgrep",
    *,
    ruleset_hash: str | None = "sha256:rules",
    advisory_db_hash: str | None = None,
    adapter_version: str = "adapter-1",
    sensor_version: str = "tool-1",
) -> SensorProvenance:
    return SensorProvenance(
        sensor_id=sensor_id,
        sensor_version=sensor_version,
        adapter_version=adapter_version,
        ruleset_hash=ruleset_hash,
        advisory_db_hash=advisory_db_hash,
        status="complete",
    )


def _sast_finding(
    rule_id: str,
    *,
    severity: str,
    sensor_id: str = "semgrep",
    ordinal: int = 0,
    source_span: SourceSpan | None = None,
) -> SASTSecurityFinding:
    components = (
        "v1",
        "sast",
        sensor_id,
        rule_id,
        "src/app.py",
        "src.app.handler",
        "eval(user_input)",
        str(ordinal),
    )
    return SASTSecurityFinding(
        category="sast",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity=severity,
        message="finding",
        rule_id=rule_id,
        module_path="src/app.py",
        qualified_name="src.app.handler",
        normalized_text="eval(user_input)",
        ordinal=ordinal,
        source_span=source_span,
    )


def _sca_finding(
    advisory_id: str,
    *,
    severity: str,
    sensor_id: str = "pip-audit",
    package_name: str = "django",
    installed_version: str = "3.2.0",
) -> SCASecurityFinding:
    components = (
        "v1",
        "sca",
        sensor_id,
        package_name,
        installed_version,
        advisory_id,
    )
    return SCASecurityFinding(
        category="sca",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity=severity,
        message="advisory",
        package_name=package_name,
        installed_version=installed_version,
        advisory_id=advisory_id,
    )


def _target_with_suppression(finding: SASTSecurityFinding, *, expires: dt.date) -> str:
    return (
        TARGET_PASS
        + "\nsecurity:\n"
        + "  suppressions:\n"
        + f"    - canonical_id: {json.dumps(finding.canonical_id)}\n"
        + f"      identity_components: {json.dumps(list(finding.identity_components))}\n"
        + "      reason: accepted test fixture finding\n"
        + f"      expires: {json.dumps(expires.isoformat())}\n"
        + "      owner: security-team\n"
    )
