from __future__ import annotations

from semantic_ci_code.repair_compiler import list_adapters, register_adapter
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
    registered = {adapter.name for adapter in list_adapters()}
    for adapter in (ClaudeCodeAdapter(), CursorAdapter(), CodexAdapter()):
        if adapter.name not in registered:
            register_adapter(adapter)
            registered.add(adapter.name)
