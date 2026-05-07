from __future__ import annotations

from semantic_ci_code.repair_compiler import register_adapter
from semantic_ci_code.repair_compiler.adapters.claude_code import ClaudeCodeAdapter

__all__ = [
    "ClaudeCodeAdapter",
    "register_builtin_adapters",
]


def register_builtin_adapters() -> None:
    register_adapter(ClaudeCodeAdapter())
