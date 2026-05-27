from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.ssp.adapters.pip_audit import PipAuditAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "pip_audit_output_basic.json"


def _basic_payload() -> object:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _adapter_result(payload: object | None = None):
    return PipAuditAdapter().from_json(
        _basic_payload() if payload is None else payload,
        requirements=None,
        repo_root=FIXTURES,
        version="2.8.0",
    )


def test_pip_audit_fixture_maps_to_sca_sensor_output():
    result = _adapter_result()

    assert result.output.sensor_id == "pip-audit"
    assert result.output.sensor_version == "2.8.0"
    assert result.output.status == "complete"
    assert result.sensor_spec.id == "pip-audit"
    assert result.sensor_spec.version == "2.8.0"
    assert result.sensor_spec.advisory_db_hash is None

    findings = {finding.advisory_id: finding for finding in result.output.findings}
    django = findings["PYSEC-2021-9"]
    assert django.package_name == "django"
    assert django.installed_version == "3.2.0"
    assert django.severity == "critical"
    assert django.message == "SQL injection in Django QuerySet."
    assert django.fingerprint is None


def test_pip_audit_one_package_with_multiple_vulns_maps_to_multiple_findings():
    result = _adapter_result()

    django_findings = [
        finding for finding in result.output.findings if finding.package_name == "django"
    ]
    assert [finding.advisory_id for finding in django_findings] == [
        "CVE-2023-36053",
        "PYSEC-2021-9",
    ]


def test_pip_audit_scan_invokes_json_output_and_detects_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[list[str]] = []
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("django==3.2.0\n", encoding="utf-8")

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert cwd == tmp_path.resolve()
        assert capture_output is True
        assert text is True
        assert check is False
        if command == ["pip-audit", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pip-audit 2.8.0\n", "")
        return subprocess.CompletedProcess(command, 1, json.dumps(_basic_payload()), "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=requirements, repo_root=tmp_path)

    assert calls[0] == ["pip-audit", "--version"]
    assert calls[1] == [
        "pip-audit",
        "--format=json",
        "--desc",
        "--requirement",
        str(requirements),
    ]
    assert result.output.status == "complete"
    assert result.output.sensor_version == "2.8.0"
    assert result.sensor_spec.version == "2.8.0"


def test_pip_audit_scan_without_requirements_audits_project_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        calls.append(command)
        if command == ["pip-audit", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pip-audit 2.8.0\n", "")
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=None, repo_root=tmp_path)

    assert calls[0] == ["pip-audit", "--version"]
    assert calls[1] == [
        "pip-audit",
        "--format=json",
        "--desc",
        str(tmp_path.resolve()),
    ]
    assert result.output.status == "complete"
    assert result.output.findings == ()


def test_pip_audit_project_path_uses_locked_when_version_supports_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        calls.append(command)
        if command == ["pip-audit", "--version"]:
            return subprocess.CompletedProcess(command, 0, "pip-audit 2.9.0\n", "")
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=None, repo_root=tmp_path)

    assert calls[0] == ["pip-audit", "--version"]
    assert calls[1] == [
        "pip-audit",
        "--format=json",
        "--desc",
        "--locked",
        str(tmp_path.resolve()),
    ]
    assert result.output.status == "complete"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (9.0, "critical"),
        (7.0, "high"),
        (4.0, "medium"),
        (0.1, "low"),
        (None, "medium"),
    ],
)
def test_pip_audit_severity_mapping_from_cvss(score: float | None, expected: str):
    vuln: dict[str, object] = {
        "id": "PYSEC-test",
        "description": "desc",
    }
    if score is not None:
        vuln["cvss_score"] = score
    payload = [{"name": "pkg", "version": "1.0", "vulns": [vuln]}]

    result = _adapter_result(payload)

    assert result.output.findings[0].severity == expected


def test_pip_audit_severity_mapping_from_named_field():
    payload = [
        {
            "name": "pkg",
            "version": "1.0",
            "vulns": [{"id": "PYSEC-test", "severity": "HIGH"}],
        }
    ]

    result = _adapter_result(payload)

    assert result.output.findings[0].severity == "high"


def test_pip_audit_severity_mapping_from_nested_severity_score():
    payload = [
        {
            "name": "pkg",
            "version": "1.0",
            "vulns": [
                {
                    "id": "PYSEC-test",
                    "severity": [{"type": "CVSS_V3", "score": "8.2"}],
                }
            ],
        }
    ]

    result = _adapter_result(payload)

    assert result.output.findings[0].severity == "high"


def test_pip_audit_numeric_severity_field_is_not_treated_as_cvss():
    payload = [
        {
            "name": "pkg",
            "version": "1.0",
            "vulns": [{"id": "PYSEC-test", "severity": 3.5}],
        }
    ]

    result = _adapter_result(payload)

    assert result.output.findings[0].severity == "medium"


def test_pip_audit_message_falls_back_to_fix_versions():
    payload = [
        {
            "name": "pkg",
            "version": "1.0",
            "vulns": [{"id": "PYSEC-test", "fix_versions": ["1.0.1", "1.1.0"]}],
        }
    ]

    result = _adapter_result(payload)

    assert result.output.findings[0].message == "fix versions: 1.0.1, 1.1.0"


@pytest.mark.parametrize("returncode", [2, 3])
def test_pip_audit_non_normal_exit_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], returncode, "[]", "boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=None, repo_root=tmp_path)

    assert result.output.status == "error"
    assert result.output.findings == ()
    assert f"code {returncode}" in (result.output.error_message or "")


def test_pip_audit_invalid_json_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, "{not json", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=None, repo_root=tmp_path)

    assert result.output.status == "error"
    assert "invalid JSON" in (result.output.error_message or "")


def test_pip_audit_missing_binary_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("pip-audit")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PipAuditAdapter().scan(requirements=None, repo_root=tmp_path)

    assert result.output.status == "error"
    assert "not found" in (result.output.error_message or "")


def test_pip_audit_hand_built_fixture_maps_minimal_result():
    payload = [
        {
            "name": "urllib3",
            "version": "1.25.0",
            "vulns": [{"id": "CVE-2099-0001", "description": "test advisory"}],
        }
    ]

    result = _adapter_result(payload)

    finding = result.output.findings[0]
    assert finding.package_name == "urllib3"
    assert finding.installed_version == "1.25.0"
    assert finding.advisory_id == "CVE-2099-0001"
    assert finding.severity == "medium"
    assert finding.fingerprint is None


def test_pip_audit_fixture_conversion_is_byte_deterministic():
    first = _adapter_result().output.model_dump(mode="json")
    second = _adapter_result().output.model_dump(mode="json")

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=False,
    )


def test_pip_audit_fixture_conversion_is_hash_seed_invariant():
    script = """
import json
import sys
from pathlib import Path
from semantic_ci_code.ssp.adapters.pip_audit import PipAuditAdapter

fixture = Path(sys.argv[1])
payload = json.loads(fixture.read_text(encoding="utf-8"))
result = PipAuditAdapter().from_json(
    payload,
    requirements=None,
    repo_root=fixture.parent,
    version="2.8.0",
)
print(json.dumps(result.output.model_dump(mode="json"), sort_keys=True, ensure_ascii=False))
"""
    outputs: list[str] = []
    for seed in ("0", "1", "random"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script, str(FIXTURE)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(completed.stdout)

    assert outputs[0] == outputs[1] == outputs[2]
