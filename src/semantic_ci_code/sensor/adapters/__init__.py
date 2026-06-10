"""Translation adapters from SSP v0.1 scan outputs to SensorState."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "PIP_AUDIT_SENSOR_ADAPTER_VERSION",
    "SEMGREP_SENSOR_ADAPTER_VERSION",
    "sensor_state_from_pip_audit_json",
    "sensor_state_from_pip_audit_scan",
    "sensor_state_from_semgrep_json",
    "sensor_state_from_semgrep_scan",
]

_EXPORT_MODULES = {
    "PIP_AUDIT_SENSOR_ADAPTER_VERSION": "semantic_ci_code.sensor.adapters.pip_audit_adapter",
    "sensor_state_from_pip_audit_json": "semantic_ci_code.sensor.adapters.pip_audit_adapter",
    "sensor_state_from_pip_audit_scan": "semantic_ci_code.sensor.adapters.pip_audit_adapter",
    "SEMGREP_SENSOR_ADAPTER_VERSION": "semantic_ci_code.sensor.adapters.semgrep_adapter",
    "sensor_state_from_semgrep_json": "semantic_ci_code.sensor.adapters.semgrep_adapter",
    "sensor_state_from_semgrep_scan": "semantic_ci_code.sensor.adapters.semgrep_adapter",
}


def __getattr__(name: str) -> Any:
    """Lazily expose non-LLM adapters so LLM fixture ingest has no live-tool imports."""

    try:
        module_name = _EXPORT_MODULES[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
