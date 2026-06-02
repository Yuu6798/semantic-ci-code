"""Translation adapters from SSP v0.1 scan outputs to SensorState."""

from semantic_ci_code.sensor.adapters.pip_audit_adapter import (
    PIP_AUDIT_SENSOR_ADAPTER_VERSION,
    sensor_state_from_pip_audit_json,
    sensor_state_from_pip_audit_scan,
)
from semantic_ci_code.sensor.adapters.semgrep_adapter import (
    SEMGREP_SENSOR_ADAPTER_VERSION,
    sensor_state_from_semgrep_json,
    sensor_state_from_semgrep_scan,
)

__all__ = [
    "PIP_AUDIT_SENSOR_ADAPTER_VERSION",
    "SEMGREP_SENSOR_ADAPTER_VERSION",
    "sensor_state_from_pip_audit_json",
    "sensor_state_from_pip_audit_scan",
    "sensor_state_from_semgrep_json",
    "sensor_state_from_semgrep_scan",
]
