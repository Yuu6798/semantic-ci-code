from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures"
RULESET = FIXTURES / "rules.yml"


def _basic_payload() -> dict[str, object]:
    return json.loads((FIXTURES / "semgrep_output_basic.json").read_text(encoding="utf-8"))


def _adapter_result(payload: dict[str, object] | None = None):
    return SemgrepAdapter().from_json(
        payload or _basic_payload(),
        target_dir=FIXTURES / "src",
        ruleset=RULESET,
        repo_root=FIXTURES,
    )


def test_semgrep_fixture_maps_to_sast_sensor_output():
    result = _adapter_result()

    assert result.output.sensor_id == "semgrep"
    assert result.output.sensor_version == "1.80.0"
    assert result.output.status == "complete"
    assert result.sensor_spec.id == "semgrep"
    assert result.sensor_spec.version == "1.80.0"
    assert (
        result.sensor_spec.ruleset_hash
        == f"sha256:{hashlib.sha256(RULESET.read_bytes()).hexdigest()}"
    )

    findings = {finding.rule_id: finding for finding in result.output.findings}
    password = findings["python.security.hardcoded-password"]
    assert password.module_path == "src/app.py"
    assert password.qualified_name == "src.app.UserService.create_user"
    assert password.severity == "medium"
    assert password.message == "Hardcoded password found"
    assert password.normalized_text == "password ='hunter2'"
    assert password.normalization == "ast"
    assert password.ordinal is None
    assert password.fingerprint is None
    assert password.source_span is not None
    assert password.source_span.sort_key() == (3, 9, 3, 29)


def test_semgrep_severity_mapping_error_warning_info():
    result = _adapter_result()

    severities = {finding.rule_id: finding.severity for finding in result.output.findings}
    assert severities == {
        "python.security.eval": "critical",
        "python.security.hardcoded-password": "medium",
        "python.style.module-secret": "info",
    }


def test_semgrep_module_level_finding_uses_module_qualified_name():
    result = _adapter_result()

    module_finding = next(
        finding
        for finding in result.output.findings
        if finding.rule_id == "python.style.module-secret"
    )
    assert module_finding.module_path == "src/module_level.py"
    assert module_finding.qualified_name == "src.module_level"


def test_semgrep_scan_invokes_determinism_flags(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = cwd
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["check"] = check
        return subprocess.CompletedProcess(command, 1, json.dumps(_basic_payload()), "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SemgrepAdapter().scan(FIXTURES / "src", ruleset=RULESET, repo_root=FIXTURES)

    assert result.output.status == "complete"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:5] == [
        "semgrep",
        "--json",
        "--metrics=off",
        "--disable-version-check",
        "--no-rewrite-rule-ids",
    ]
    assert "--config" in command
    assert captured["cwd"] == FIXTURES
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False


@pytest.mark.parametrize("returncode", [2, 3])
def test_semgrep_non_normal_exit_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], returncode, "{}", "boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SemgrepAdapter().scan(FIXTURES / "src", ruleset=RULESET, repo_root=FIXTURES)

    assert result.output.status == "error"
    assert result.output.findings == ()
    assert f"code {returncode}" in (result.output.error_message or "")


def test_semgrep_invalid_json_returns_error(monkeypatch: pytest.MonkeyPatch):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, "{not json", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SemgrepAdapter().scan(FIXTURES / "src", ruleset=RULESET, repo_root=FIXTURES)

    assert result.output.status == "error"
    assert "invalid JSON" in (result.output.error_message or "")


def test_semgrep_missing_binary_returns_error(monkeypatch: pytest.MonkeyPatch):
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("semgrep")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SemgrepAdapter().scan(FIXTURES / "src", ruleset=RULESET, repo_root=FIXTURES)

    assert result.output.status == "error"
    assert "not found" in (result.output.error_message or "")


def test_semgrep_module_path_normalizes_backslashes(tmp_path: Path):
    source = tmp_path / "src" / "pkg" / "win.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src\\pkg\\win.py"]},
        "results": [
            {
                "check_id": "rule",
                "path": "src\\pkg\\win.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {
                    "message": "msg",
                    "severity": "INFO",
                    "lines": "return 1",
                },
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=tmp_path / "src",
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    finding = result.output.findings[0]
    assert finding.module_path == "src/pkg/win.py"
    assert finding.qualified_name == "src.pkg.win.f"


def test_semgrep_target_relative_path_resolves_under_target_dir(tmp_path: Path):
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["app.py"]},
        "results": [
            {
                "check_id": "target-relative",
                "path": "app.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {
                    "message": "msg",
                    "severity": "INFO",
                    "lines": "return 1",
                },
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=tmp_path / "src",
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    finding = result.output.findings[0]
    assert finding.module_path == "src/app.py"
    assert finding.qualified_name == "src.app.f"


def test_semgrep_relative_target_dir_resolves_against_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo = tmp_path / "repo"
    source = repo / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    ruleset = repo / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src/app.py"]},
        "results": [
            {
                "check_id": "repo-relative",
                "path": "src/app.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {
                    "message": "msg",
                    "severity": "INFO",
                    "lines": "return 1",
                },
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=Path("src"),
        ruleset=Path("rules.yml"),
        repo_root=repo,
    )

    finding = result.output.findings[0]
    assert finding.module_path == "src/app.py"
    assert finding.qualified_name == "src.app.f"
    assert (
        result.sensor_spec.ruleset_hash
        == f"sha256:{hashlib.sha256(ruleset.read_bytes()).hexdigest()}"
    )


def test_semgrep_target_relative_path_resolves_for_single_file_target(tmp_path: Path):
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["app.py"]},
        "results": [
            {
                "check_id": "single-file",
                "path": "app.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {
                    "message": "msg",
                    "severity": "INFO",
                    "lines": "return 1",
                },
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=source,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    finding = result.output.findings[0]
    assert finding.module_path == "src/app.py"
    assert finding.qualified_name == "src.app.f"


def test_semgrep_missing_scanned_target_file_returns_error(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "scanned.py").write_text("def scanned():\n    pass\n", encoding="utf-8")
    (src / "missing.py").write_text("def missing():\n    pass\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src/scanned.py"]},
        "results": [],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=src,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    assert result.output.status == "error"
    assert result.output.findings == ()
    assert "src/missing.py" in (result.output.error_message or "")


def test_semgrep_missing_scanned_paths_report_returns_error(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def app():\n    pass\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {"version": "1.80.0", "results": []}

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=src,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    assert result.output.status == "error"
    assert result.output.findings == ()
    assert "did not report scanned paths" in (result.output.error_message or "")


def test_semgrep_missing_extra_lines_falls_back_to_source_span(tmp_path: Path):
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src/app.py"]},
        "results": [
            {
                "check_id": "missing-lines",
                "path": "src/app.py",
                "start": {"line": 2, "col": 5},
                "end": {"line": 2, "col": 13},
                "extra": {
                    "message": "msg",
                    "severity": "INFO",
                },
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=tmp_path / "src",
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    finding = result.output.findings[0]
    assert finding.normalized_text == "return 1"
    assert finding.normalization == "ast"


def test_semgrep_top_level_errors_return_error(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def app():\n    pass\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "version": "1.80.0",
        "paths": {"scanned": ["src/app.py"]},
        "errors": [{"type": "ParseError", "message": "failed to parse app.py"}],
        "results": [],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=src,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    assert result.output.status == "error"
    assert result.output.findings == ()
    assert "failed to parse app.py" in (result.output.error_message or "")


def test_semgrep_hand_built_fixture_maps_minimal_result(tmp_path: Path):
    source = tmp_path / "pkg.py"
    source.write_text("value = input()\n", encoding="utf-8")
    ruleset = tmp_path / "rules.yml"
    ruleset.write_text("rules: []\n", encoding="utf-8")
    payload = {
        "paths": {"scanned": ["pkg.py"]},
        "results": [
            {
                "check_id": "hand-built",
                "path": "pkg.py",
                "start": {"line": 1, "col": 1},
                "end": {"line": 1, "col": 15},
                "extra": {"severity": "INFO", "lines": "value = input()"},
            }
        ],
    }

    result = SemgrepAdapter().from_json(
        payload,
        target_dir=tmp_path,
        ruleset=ruleset,
        repo_root=tmp_path,
    )

    finding = result.output.findings[0]
    assert finding.rule_id == "hand-built"
    assert finding.qualified_name == "pkg"
    assert finding.message == ""


def test_semgrep_fixture_conversion_is_byte_deterministic():
    first = _adapter_result().output.model_dump(mode="json")
    second = _adapter_result().output.model_dump(mode="json")

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=False,
    )


def test_semgrep_fixture_conversion_is_hash_seed_invariant():
    script = """
import json
import sys
from pathlib import Path
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter

fixtures = Path(sys.argv[1])
payload = json.loads((fixtures / "semgrep_output_basic.json").read_text(encoding="utf-8"))
result = SemgrepAdapter().from_json(
    payload,
    target_dir=fixtures / "src",
    ruleset=fixtures / "rules.yml",
    repo_root=fixtures,
)
print(json.dumps(result.output.model_dump(mode="json"), sort_keys=True, ensure_ascii=False))
"""
    outputs: list[str] = []
    for seed in ("0", "1", "random"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script, str(FIXTURES)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.append(completed.stdout)

    assert outputs[0] == outputs[1] == outputs[2]
