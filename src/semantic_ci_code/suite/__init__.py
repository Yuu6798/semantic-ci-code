"""Suite-level integration for code and security verdicts."""

from semantic_ci_code.suite.evaluator import SuiteResult, SuiteVerdict, combine_verdict
from semantic_ci_code.suite.security import evaluate_security

__all__ = [
    "SuiteResult",
    "SuiteVerdict",
    "combine_verdict",
    "evaluate_security",
]
