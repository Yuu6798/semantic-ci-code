"""LLM scout adapter protocol and deterministic projection helpers."""

from semantic_ci_code.sensor.adapters.llm.aggregate import (
    LLM_ENSEMBLE_ADAPTER_VERSION,
    LLM_ENSEMBLE_SENSOR_ID,
    LLMEnsembleAggregation,
    aggregate_advisory_states,
)
from semantic_ci_code.sensor.adapters.llm.codex_security import (
    CODEX_SECURITY_SENSOR_ADAPTER_VERSION,
    CODEX_SECURITY_SENSOR_ID,
    CodexSecurityAdapter,
    sensor_state_from_codex_security_json,
)
from semantic_ci_code.sensor.adapters.llm.protocol import (
    CodeView,
    LLMSensorAdapter,
    LLMSensorProvenance,
    RawLLMFinding,
    project_to_canonical,
)

__all__ = [
    "CODEX_SECURITY_SENSOR_ADAPTER_VERSION",
    "CODEX_SECURITY_SENSOR_ID",
    "LLM_ENSEMBLE_ADAPTER_VERSION",
    "LLM_ENSEMBLE_SENSOR_ID",
    "CodexSecurityAdapter",
    "CodeView",
    "LLMEnsembleAggregation",
    "LLMSensorAdapter",
    "LLMSensorProvenance",
    "RawLLMFinding",
    "aggregate_advisory_states",
    "project_to_canonical",
    "sensor_state_from_codex_security_json",
]
