from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ADVISORY_CODES = (
    "ADVISORY-D1",
    "ADVISORY-D3",
    "ADVISORY-D4",
    "ADVISORY-D6",
    "ADVISORY-D7",
    "ADVISORY-I1",
    "ADVISORY-P1",
    "ADVISORY-P2",
    "ADVISORY-S1",
)


@dataclass(frozen=True)
class Advisory:
    code: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"

    def __post_init__(self) -> None:
        if self.code not in ADVISORY_CODES:
            raise ValueError(f"unknown advisory code: {self.code}")
        if self.severity != "info":
            raise ValueError(f"advisor surface emits severity=info only; got {self.severity!r}")
