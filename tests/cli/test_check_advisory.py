from __future__ import annotations

import json
from pathlib import Path

from semantic_ci_code.sensor.adapters.llm import (
    CODEX_SECURITY_SENSOR_ID,
    LLM_ENSEMBLE_SENSOR_ID,
    sensor_state_from_codex_security_json,
)
from semantic_ci_code.sensor.models import SensorProvenance, SensorState, canonical_id_for_identity

from .git_helpers import TARGET_PASS, TARGET_REPAIR, git, write_file
from .helpers import payload, run_semantic_ci

_EXPECTED_PROPERTY = "requires authorization guard"


def test_check_advisory_json_surfaces_added_and_pre_existing_findings(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(
            _missing_authz_payload(qualified_name="mod.existing"),
            _missing_authz_payload(
                finding_class="missing-rate-limit",
                qualified_name="mod.added",
                expected_property="requires rate limit",
            ),
        ),
    )

    result = _run_check_with_advisory(repo, advisory_payload)

    assert result.returncode == 0
    data = payload(result)
    assert data["verdict"] == "pass"
    assert "suite_verdict" not in data
    advisory = data["advisory"]
    assert advisory["adapter_id"] == CODEX_SECURITY_SENSOR_ID
    assert advisory["sensor"] == {
        "sensor_id": CODEX_SECURITY_SENSOR_ID,
        "sensor_version": "codex-security-test-1",
        "model_id": "codex-security-test-model",
        "prompt_hash": "sha256:test-prompt",
        "non_reproducible": True,
        "status": "complete",
        "error_message": None,
    }
    assert advisory["counts"] == {
        "scouted": 2,
        "surfaced": 2,
        "pre_existing": 0,
        "muted": 0,
    }
    assert {finding["qualified_name"] for finding in advisory["surfaced"]} == {
        "mod.added",
        "mod.existing",
    }
    assert advisory["pre_existing"] == []
    assert advisory["muted"] == []
    assert advisory["mutes_path"] is None
    assert "members" not in advisory

    pre_existing_repo = _init_advisory_repo(
        tmp_path / "pre-existing",
        baseline_has_guard=False,
    )
    pre_existing_result = _run_check_with_advisory(pre_existing_repo, advisory_payload)

    assert pre_existing_result.returncode == 0
    pre_existing_advisory = payload(pre_existing_result)["advisory"]
    assert pre_existing_advisory["counts"] == {
        "scouted": 2,
        "surfaced": 1,
        "pre_existing": 1,
        "muted": 0,
    }
    assert pre_existing_advisory["pre_existing"][0]["qualified_name"] == "mod.existing"


def test_check_advisory_mute_filters_active_finding_and_records_audit(
    tmp_path: Path,
):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    canonical_id = _llm_canonical_id(qualified_name="mod.existing")
    mutes = _write_mutes(
        tmp_path / "advisory_mutes.yaml",
        canonical_id=canonical_id,
        expires="2026-09-01",
    )

    result = _run_check_with_advisory(repo, advisory_payload, mutes=mutes)

    assert result.returncode == 0
    advisory = payload(result)["advisory"]
    assert advisory["surfaced"] == []
    assert advisory["counts"] == {
        "scouted": 1,
        "surfaced": 0,
        "pre_existing": 0,
        "muted": 1,
    }
    assert advisory["muted"] == [
        {
            "canonical_id": canonical_id,
            "reason": "accepted fixture scout finding",
            "owner": "security-team",
            "expires": "2026-09-01",
        }
    ]
    assert advisory["mutes_path"] == str(mutes)

    expired = _write_mutes(
        tmp_path / "expired_mutes.yaml",
        canonical_id=canonical_id,
        expires="2026-08-31",
    )
    expired_result = _run_check_with_advisory(repo, advisory_payload, mutes=expired)

    assert expired_result.returncode == 0
    expired_advisory = payload(expired_result)["advisory"]
    assert expired_advisory["counts"]["surfaced"] == 1
    assert expired_advisory["counts"]["muted"] == 0


def test_check_advisory_non_complete_sensor_does_not_change_exit(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security-error.json",
        status="error",
        error_message="recorded Codex Security run failed",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )

    result = _run_check_with_advisory(repo, advisory_payload)

    assert result.returncode == 0
    advisory = payload(result)["advisory"]
    assert advisory["sensor"]["status"] == "error"
    assert advisory["sensor"]["error_message"] == "recorded Codex Security run failed"
    assert advisory["counts"] == {
        "scouted": 0,
        "surfaced": 0,
        "pre_existing": 0,
        "muted": 0,
    }
    assert advisory["surfaced"] == []


def test_check_advisory_human_output_marks_advisory_as_non_blocking(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )

    result = _run_check_with_advisory(repo, advisory_payload, output_format="human")

    assert result.returncode == 0
    assert "Advisory scout:" in result.stdout
    assert "findings do not affect verdict or exit code" in result.stdout
    assert "+ missing-authz [critical]" in result.stdout
    assert "mod.py:1 (absence) - missing authorization guard" in result.stdout


def test_check_advisory_rejects_unsupported_formats_and_bad_flags(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )

    sarif = _run_check_with_advisory(repo, advisory_payload, output_format="sarif")
    assert sarif.returncode == 2
    assert "advisory output is deferred" in sarif.stderr

    gh_actions = _run_check_with_advisory(repo, advisory_payload, output_format="gh-actions")
    assert gh_actions.returncode == 2
    assert "advisory output is deferred" in gh_actions.stderr

    mutes_without_sensor = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
        "--advisory-mutes",
        str(tmp_path / "advisory_mutes.yaml"),
    )
    assert mutes_without_sensor.returncode == 2
    assert "--advisory-mutes is only valid with --advisory-sensor" in mutes_without_sensor.stderr

    unknown = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
        "--advisory-sensor",
        f"other={advisory_payload}",
    )
    assert unknown.returncode == 2
    assert "unknown advisory sensor adapter" in unknown.stderr

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    invalid_json = _run_check_with_advisory(repo, bad_json)
    assert invalid_json.returncode == 2
    assert "payload must be valid JSON" in invalid_json.stderr


def test_check_advisory_can_run_with_verdict_bearing_sensor_flags(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    sensor_baseline = _write_empty_sensor_state(tmp_path / "sensor-baseline.json")
    sensor_candidate = _write_empty_sensor_state(tmp_path / "sensor-candidate.json")

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
        "--sensor-baseline",
        str(sensor_baseline),
        "--sensor-candidate",
        str(sensor_candidate),
        "--advisory-sensor",
        f"{CODEX_SECURITY_SENSOR_ID}={advisory_payload}",
        "--as-of",
        "2026-09-01",
    )

    assert result.returncode == 0
    data = payload(result)
    assert data["security"]["verdict"] == "pass"
    assert data["suite_verdict"] == "pass"
    assert data["advisory"]["counts"]["surfaced"] == 1


def test_check_multiple_advisory_sensors_use_ensemble_and_members(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    first = _write_codex_payload(
        tmp_path / "codex-security-a.json",
        model_id="codex-security-a",
        prompt_hash="sha256:prompt-a",
        findings=(
            _missing_authz_payload(
                qualified_name="mod.existing",
                severity="low",
                message="low confidence scout",
            ),
        ),
    )
    second = _write_codex_payload(
        tmp_path / "codex-security-b.json",
        model_id="codex-security-b",
        prompt_hash="sha256:prompt-b",
        findings=(
            _missing_authz_payload(
                qualified_name="mod.existing",
                severity="critical",
                message="critical scout",
            ),
        ),
    )

    result = _run_check_with_advisory(repo, (first, second))

    assert result.returncode == 0
    advisory = payload(result)["advisory"]
    assert advisory["adapter_id"] == LLM_ENSEMBLE_SENSOR_ID
    assert advisory["sensor"]["sensor_id"] == LLM_ENSEMBLE_SENSOR_ID
    assert advisory["sensor"]["model_id"] == "ensemble:codex-security-a,codex-security-b"
    assert len(advisory["members"]) == 2
    assert [member["model_id"] for member in advisory["members"]] == [
        "codex-security-a",
        "codex-security-b",
    ]
    assert advisory["counts"] == {
        "scouted": 1,
        "surfaced": 1,
        "pre_existing": 0,
        "muted": 0,
    }
    assert advisory["surfaced"][0]["sensor_id"] == LLM_ENSEMBLE_SENSOR_ID
    assert advisory["surfaced"][0]["severity"] == "critical"
    assert advisory["surfaced"][0]["message"] == "low confidence scout"


def test_check_ensemble_advisory_mutes_match_ensemble_canonical_id(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    first = _write_codex_payload(
        tmp_path / "codex-security-a.json",
        model_id="codex-security-a",
        prompt_hash="sha256:prompt-a",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    second = _write_codex_payload(
        tmp_path / "codex-security-b.json",
        model_id="codex-security-b",
        prompt_hash="sha256:prompt-b",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    ensemble_canonical_id = _llm_canonical_id(
        sensor_id=LLM_ENSEMBLE_SENSOR_ID,
        qualified_name="mod.existing",
    )
    mutes = _write_mutes(
        tmp_path / "ensemble_mutes.yaml",
        canonical_id=ensemble_canonical_id,
        sensor_id=LLM_ENSEMBLE_SENSOR_ID,
        expires="2026-09-01",
    )

    result = _run_check_with_advisory(repo, (first, second), mutes=mutes)

    assert result.returncode == 0
    advisory = payload(result)["advisory"]
    assert advisory["surfaced"] == []
    assert advisory["counts"] == {
        "scouted": 1,
        "surfaced": 0,
        "pre_existing": 0,
        "muted": 1,
    }
    assert advisory["muted"][0]["canonical_id"] == ensemble_canonical_id


def test_check_rejects_llm_state_on_verdict_bearing_sensor_path(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    advisory_payload = _write_codex_payload(
        tmp_path / "codex-security.json",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    baseline_sensor = _write_empty_sensor_state(tmp_path / "sensor-baseline.json")
    llm_state = sensor_state_from_codex_security_json(
        json.loads(advisory_payload.read_text(encoding="utf-8"))
    )
    candidate_sensor = tmp_path / "sensor-candidate-llm.json"
    candidate_sensor.write_text(llm_state.model_dump_json(), encoding="utf-8")

    result = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
        "--sensor-baseline",
        str(baseline_sensor),
        "--sensor-candidate",
        str(candidate_sensor),
        "--as-of",
        "2026-09-01",
    )

    assert result.returncode == 2
    assert "LLM findings are advisory-only and cannot enter verdict security delta" in result.stderr


def test_check_advisory_does_not_change_verdict_summary_or_exit_code(tmp_path: Path):
    repo = _init_advisory_repo(tmp_path, baseline_has_guard=True)
    first = _write_codex_payload(
        tmp_path / "codex-security-a.json",
        model_id="codex-security-a",
        prompt_hash="sha256:prompt-a",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    second = _write_codex_payload(
        tmp_path / "codex-security-b.json",
        model_id="codex-security-b",
        prompt_hash="sha256:prompt-b",
        findings=(_missing_authz_payload(qualified_name="mod.existing"),),
    )
    advisory_payloads = (first, second)

    without_advisory = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
    )
    with_advisory = _run_check_with_advisory(repo, advisory_payloads)

    assert without_advisory.returncode == with_advisory.returncode
    without_payload = payload(without_advisory)
    with_payload = payload(with_advisory)
    for key in ("verdict", "repair_plan", "summary"):
        assert without_payload[key] == with_payload[key]

    write_file(repo / "target.yaml", TARGET_REPAIR)
    repair_without_advisory = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        "json",
        "--strict-repair",
    )
    repair_with_advisory = _run_check_with_advisory(
        repo,
        advisory_payloads,
        strict_repair=True,
    )

    assert repair_without_advisory.returncode == repair_with_advisory.returncode == 1
    repair_without_payload = payload(repair_without_advisory)
    repair_with_payload = payload(repair_with_advisory)
    for key in ("verdict", "repair_plan", "summary"):
        assert repair_without_payload[key] == repair_with_payload[key]


def _init_advisory_repo(tmp_path: Path, *, baseline_has_guard: bool) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Semantic CI")
    git(repo, "config", "user.email", "semantic-ci@example.invalid")
    write_file(repo / "mod.py", _source(has_guard=baseline_has_guard, include_added=False))
    write_file(repo / "target.yaml", TARGET_PASS)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    baseline_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "update-ref", "refs/remotes/origin/main", baseline_sha)
    git(repo, "switch", "-c", "feature")
    write_file(repo / "mod.py", _source(has_guard=False, include_added=True))
    git(repo, "add", ".")
    git(repo, "commit", "-m", "candidate")
    return repo


def _source(*, has_guard: bool, include_added: bool) -> str:
    decorator = "@login_required\n" if has_guard else ""
    added = "\n\ndef added() -> int:\n    return 2\n" if include_added else ""
    return (
        "def login_required(fn):\n"
        "    return fn\n\n\n"
        f"{decorator}"
        "def existing() -> int:\n"
        "    return 1\n"
        f"{added}"
    )


def _run_check_with_advisory(
    repo: Path,
    advisory_payload: Path | tuple[Path, ...],
    *,
    mutes: Path | None = None,
    output_format: str = "json",
    strict_repair: bool = False,
):
    args = [
        "check",
        "--mode",
        "smoke",
        "--no-fetch",
        "--no-cache",
        "--format",
        output_format,
        "--as-of",
        "2026-09-01",
    ]
    payloads = advisory_payload if isinstance(advisory_payload, tuple) else (advisory_payload,)
    for payload_path in payloads:
        args.extend(("--advisory-sensor", f"{CODEX_SECURITY_SENSOR_ID}={payload_path}"))
    if mutes is not None:
        args.extend(("--advisory-mutes", str(mutes)))
    if strict_repair:
        args.append("--strict-repair")
    return run_semantic_ci(repo, *args)


def _write_codex_payload(
    path: Path,
    *,
    model_id: str = "codex-security-test-model",
    prompt_hash: str = "sha256:test-prompt",
    sensor_version: str = "codex-security-test-1",
    status: str = "complete",
    error_message: str | None = None,
    findings: tuple[dict[str, object], ...],
) -> Path:
    path.write_text(
        json.dumps(
            {
                "sensor_version": sensor_version,
                "model_id": model_id,
                "prompt_hash": prompt_hash,
                "status": status,
                "error_message": error_message,
                "findings": list(findings),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _missing_authz_payload(
    *,
    finding_class: str = "missing-authz",
    qualified_name: str,
    expected_property: str = _EXPECTED_PROPERTY,
    severity: str = "critical",
    message: str = "missing authorization guard",
) -> dict[str, object]:
    return {
        "finding_class": finding_class,
        "module_path": "mod.py",
        "qualified_name": qualified_name,
        "anchor_kind": "absence",
        "expected_property": expected_property,
        "severity": severity,
        "message": message,
        "source_span": {
            "start_line": 1,
            "end_line": 1,
            "start_col": 0,
            "end_col": 1,
        },
    }


def _llm_canonical_id(
    *,
    qualified_name: str,
    sensor_id: str = CODEX_SECURITY_SENSOR_ID,
    finding_class: str = "missing-authz",
    ordinal: int = 0,
    expected_property: str = _EXPECTED_PROPERTY,
) -> str:
    return canonical_id_for_identity(
        (
            "v1",
            "llm",
            sensor_id,
            finding_class,
            "mod.py",
            qualified_name,
            "absence",
            expected_property,
            str(ordinal),
        )
    )


def _write_mutes(
    path: Path,
    *,
    canonical_id: str,
    expires: str,
    sensor_id: str = CODEX_SECURITY_SENSOR_ID,
) -> Path:
    path.write_text(
        "\n".join(
            (
                "mutes:",
                f"  - canonical_id: {json.dumps(canonical_id)}",
                "    identity_components:",
                "      - v1",
                "      - llm",
                f"      - {sensor_id}",
                "      - missing-authz",
                "      - mod.py",
                "      - mod.existing",
                "      - absence",
                f"      - {json.dumps(_EXPECTED_PROPERTY)}",
                "      - '0'",
                "    reason: accepted fixture scout finding",
                f"    expires: {expires}",
                "    owner: security-team",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


def _write_empty_sensor_state(path: Path) -> Path:
    state = SensorState(
        provenance_by_sensor={
            "semgrep": SensorProvenance(
                sensor_id="semgrep",
                sensor_version="semgrep-test",
                adapter_version="adapter-test",
                ruleset_hash="sha256:test-rules",
                status="complete",
            )
        },
        findings=(),
    )
    path.write_text(state.model_dump_json(), encoding="utf-8")
    return path
