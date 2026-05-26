"""Semantic Security Protocol (SSP) v0.1 data layer."""

from semantic_ci_code.ssp.delta import assign_sast_ordinals, compute_delta
from semantic_ci_code.ssp.fingerprint import sast_fingerprint, sca_fingerprint
from semantic_ci_code.ssp.models import (
    Finding,
    SASTFinding,
    SCAFinding,
    ScanEndpoint,
    SensorOutput,
    SensorSpec,
    SourceSpan,
    SSPDelta,
    SSPEngine,
    SSPEnvelope,
    SSPVerdict,
)
from semantic_ci_code.ssp.python_profile import normalize_text
from semantic_ci_code.ssp.verdict import aggregate_verdict, build_verdict, verdict_for_delta

__all__ = [
    "Finding",
    "SASTFinding",
    "SCAFinding",
    "SSPDelta",
    "SSPEngine",
    "SSPEnvelope",
    "SSPVerdict",
    "ScanEndpoint",
    "SensorOutput",
    "SensorSpec",
    "SourceSpan",
    "aggregate_verdict",
    "assign_sast_ordinals",
    "build_verdict",
    "compute_delta",
    "normalize_text",
    "sast_fingerprint",
    "sca_fingerprint",
    "verdict_for_delta",
]
