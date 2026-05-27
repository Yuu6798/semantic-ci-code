"""Sensor adapters for Semantic Security Protocol (SSP)."""

from semantic_ci_code.ssp.adapters.pip_audit import PipAuditAdapter, PipAuditScanResult
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter, SemgrepScanResult

__all__ = [
    "PipAuditAdapter",
    "PipAuditScanResult",
    "SemgrepAdapter",
    "SemgrepScanResult",
]
