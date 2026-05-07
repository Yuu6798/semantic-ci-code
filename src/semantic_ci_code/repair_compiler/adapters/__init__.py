from __future__ import annotations

from semantic_ci_code.repair_compiler import register_adapter
from semantic_ci_code.repair_compiler.adapters.claude_code import ClaudeCodeAdapter
from semantic_ci_code.repair_compiler.adapters.codex import CodexAdapter
from semantic_ci_code.repair_compiler.adapters.cursor import CursorAdapter

__all__ = [
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CursorAdapter",
    "register_builtin_adapters",
]


def register_builtin_adapters() -> None:
    register_adapter(ClaudeCodeAdapter())
    register_adapter(CursorAdapter())
    register_adapter(CodexAdapter())
