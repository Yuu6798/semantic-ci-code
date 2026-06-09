"""LLM scout adapter protocol and deterministic projection helpers."""

from semantic_ci_code.sensor.adapters.llm.protocol import (
    CodeView,
    LLMSensorAdapter,
    RawLLMFinding,
    project_to_canonical,
)

__all__ = [
    "CodeView",
    "LLMSensorAdapter",
    "RawLLMFinding",
    "project_to_canonical",
]
