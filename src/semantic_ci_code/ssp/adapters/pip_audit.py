"""pip-audit adapter for SSP SCA sensor output."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from semantic_ci_code.ssp.adapters.dependency_sources import (
    DependencySource,
    DependencySourceError,
    generated_requirements_for_source,
)
from semantic_ci_code.ssp.models import SCAFinding, SensorOutput, SensorSpec, Severity

_PIP_AUDIT_COMMAND = "pip-audit"
_PIP_AUDIT_NORMAL_EXIT_CODES = frozenset({0, 1})


@dataclass(frozen=True)
class PipAuditScanResult:
    """pip-audit scan output plus the sensor spec used by SSP envelopes."""

    output: SensorOutput
    sensor_spec: SensorSpec


class PipAuditAdapter:
    """Run pip-audit and convert JSON results into SSP SCA findings."""

    sensor_id = "pip-audit"

    def scan(
        self,
        *,
        source: DependencySource,
        repo_root: Path,
    ) -> PipAuditScanResult:
        """Invoke pip-audit and return deterministic SSP sensor output."""

        resolved_repo_root = repo_root.resolve()
        resolved_requirements = source.path if source.kind == "requirements" else None
        version = _detect_version(cwd=resolved_repo_root)
        try:
            command, temp_dir = _command_for_source(source, version=version)
        except DependencySourceError as exc:
            return self._error_result(str(exc), version=version)

        try:
            try:
                completed = subprocess.run(
                    command,
                    cwd=resolved_repo_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                if temp_dir is not None:
                    temp_dir.cleanup()
        except FileNotFoundError as exc:
            return self._error_result("pip-audit executable not found", error=exc)

        if completed.returncode not in _PIP_AUDIT_NORMAL_EXIT_CODES:
            return self._error_result(
                f"pip-audit exited with code {completed.returncode}: {completed.stderr.strip()}",
                version=version,
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return self._error_result(
                f"pip-audit returned invalid JSON: {exc}",
                version=version,
            )

        return self.from_json(
            payload,
            requirements=resolved_requirements,
            repo_root=resolved_repo_root,
            version=version,
        )

    def from_json(
        self,
        payload: Any,
        *,
        requirements: Path | None,
        repo_root: Path,
        version: str = "",
        advisory_db_hash: str | None = None,
    ) -> PipAuditScanResult:
        """Convert a pip-audit JSON payload into SSP sensor output."""

        # Keep the adapter API symmetric with scan() and SemgrepAdapter.from_json().
        # pip-audit package payloads are environment-level SCA data, so conversion
        # does not need path reconciliation against these inputs.
        del requirements, repo_root
        try:
            findings = tuple(
                sorted(
                    (
                        finding
                        for package in _package_items(payload)
                        for finding in _findings_from_package(package)
                    ),
                    key=_finding_sort_key,
                )
            )
        except (TypeError, ValidationError, ValueError) as exc:
            return self._error_result(
                f"invalid pip-audit JSON payload: {exc}",
                version=version,
                advisory_db_hash=advisory_db_hash,
            )

        output = SensorOutput(
            sensor_id=self.sensor_id,
            sensor_version=version,
            status="complete",
            findings=findings,
        )
        sensor_spec = SensorSpec(
            id=self.sensor_id,
            version=version,
            advisory_db_hash=advisory_db_hash,
        )
        return PipAuditScanResult(output=output, sensor_spec=sensor_spec)

    def _error_result(
        self,
        message: str,
        *,
        version: str = "",
        advisory_db_hash: str | None = None,
        error: BaseException | None = None,
    ) -> PipAuditScanResult:
        detail = f"{message}: {error}" if error is not None else message
        output = SensorOutput(
            sensor_id=self.sensor_id,
            sensor_version=version,
            status="error",
            findings=(),
            error_message=detail,
        )
        sensor_spec = SensorSpec(
            id=self.sensor_id,
            version=version,
            advisory_db_hash=advisory_db_hash,
        )
        return PipAuditScanResult(output=output, sensor_spec=sensor_spec)


def _detect_version(*, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            [_PIP_AUDIT_COMMAND, "--version"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if completed.returncode != 0:
        return ""
    text = completed.stdout.strip() or completed.stderr.strip()
    if not text:
        return ""
    return text.split()[-1]


def _supports_locked_project_scan(version: str) -> bool:
    parts: list[int] = []
    for raw_part in version.split(".")[:2]:
        digits = ""
        for char in raw_part:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            return False
        parts.append(int(digits))
    if len(parts) < 2:
        return False
    major, minor = parts
    return major > 2 or (major == 2 and minor >= 9)


def _command_for_source(
    source: DependencySource,
    *,
    version: str,
) -> tuple[list[str], tempfile.TemporaryDirectory[str] | None]:
    command = [_PIP_AUDIT_COMMAND, "--format=json", "--desc"]
    if source.kind == "error":
        raise DependencySourceError(source.error_message or "dependency source parse failed")
    if source.kind == "requirements":
        if source.path is None:
            raise DependencySourceError("requirements source missing path")
        command.extend(("--requirement", str(source.path)))
        return command, None
    if source.kind in {"pylock", "fallback"}:
        if _supports_locked_project_scan(version):
            command.extend(("--locked", str(source.root)))
        else:
            command.append(str(source.root))
        return command, None
    if source.kind in {"uv-lock", "pdm-lock", "poetry-lock", "pyproject"}:
        return _command_for_generated_requirements(command, source)
    raise DependencySourceError(f"unsupported dependency source kind: {source.kind}")


def _command_for_generated_requirements(
    command: list[str],
    source: DependencySource,
) -> tuple[list[str], tempfile.TemporaryDirectory[str]]:
    generated = generated_requirements_for_source(source)
    temp_dir = tempfile.TemporaryDirectory()
    requirements = Path(temp_dir.name) / "requirements.txt"
    requirements.write_text(_requirements_text(generated.lines), encoding="utf-8")
    command.extend(("--requirement", str(requirements)))
    if generated.no_deps:
        command.append("--no-deps")
    return command, temp_dir


def _requirements_text(lines: tuple[str, ...]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _package_items(payload: Any) -> tuple[Mapping[str, Any], ...]:
    packages: object
    if isinstance(payload, Mapping):
        packages = (
            payload.get("dependencies") or payload.get("packages") or payload.get("results") or ()
        )
    else:
        packages = payload
    if not isinstance(packages, Sequence) or isinstance(packages, (str, bytes)):
        return ()
    return tuple(package for package in packages if isinstance(package, Mapping))


def _findings_from_package(package: Mapping[str, Any]) -> tuple[SCAFinding, ...]:
    package_name = str(package.get("name", ""))
    installed_version = str(package.get("version", ""))
    vulns = package.get("vulns", ())
    if not isinstance(vulns, Sequence) or isinstance(vulns, (str, bytes)):
        return ()
    return tuple(
        _finding_from_vuln(
            vuln,
            package_name=package_name,
            installed_version=installed_version,
        )
        for vuln in vulns
        if isinstance(vuln, Mapping)
    )


def _finding_from_vuln(
    vuln: Mapping[str, Any],
    *,
    package_name: str,
    installed_version: str,
) -> SCAFinding:
    return SCAFinding(
        package_name=package_name,
        installed_version=installed_version,
        advisory_id=str(vuln.get("id", "")),
        fingerprint=None,
        severity=_severity_for_vuln(vuln),
        message=_message_for_vuln(vuln),
    )


def _severity_for_vuln(vuln: Mapping[str, Any]) -> Severity:
    score = _cvss_score(vuln)
    if score is None:
        score = _cvss_score_from_severity_metadata(vuln.get("severity"))
    if score is not None:
        return _severity_from_cvss(score)

    named = _named_severity(vuln.get("severity"))
    if named is not None:
        return named
    return "medium"


def _cvss_score(value: object) -> float | None:
    if isinstance(value, Mapping):
        for key in ("cvss_score", "cvss", "score", "value"):
            score = _cvss_score(value.get(key))
            if score is not None:
                return score
        return None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            score = _cvss_score(item)
            if score is not None:
                return score
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _cvss_score_from_severity_metadata(value: object) -> float | None:
    if isinstance(value, Mapping):
        return _cvss_score(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            if isinstance(item, Mapping):
                score = _cvss_score(item)
                if score is not None:
                    return score
    return None


def _severity_from_cvss(score: float) -> Severity:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "medium"


def _named_severity(value: object) -> Severity | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"critical", "high", "medium", "low", "info"}:
        return normalized  # type: ignore[return-value]
    return None


def _message_for_vuln(vuln: Mapping[str, Any]) -> str:
    description = vuln.get("description")
    if isinstance(description, str) and description:
        return description
    fix_versions = vuln.get("fix_versions")
    if isinstance(fix_versions, Sequence) and not isinstance(fix_versions, (str, bytes)):
        versions = ", ".join(str(version) for version in fix_versions)
        if versions:
            return f"fix versions: {versions}"
    return ""


def _finding_sort_key(finding: SCAFinding) -> tuple[str, str, str, str]:
    return (
        finding.package_name,
        finding.installed_version,
        finding.advisory_id,
        finding.message,
    )
