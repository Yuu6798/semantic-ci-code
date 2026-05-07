from __future__ import annotations

import pytest

import semantic_ci_code.repair_compiler as registry
from semantic_ci_code.repair_compiler.adapters import (
    ClaudeCodeAdapter,
    CursorAdapter,
    register_builtin_adapters,
)


@pytest.fixture(autouse=True)
def isolated_registry():
    registry._ADAPTERS.clear()
    yield
    registry._ADAPTERS.clear()


def test_register_and_get_adapter():
    adapter = ClaudeCodeAdapter()

    registry.register_adapter(adapter)

    assert registry.get_adapter("claude-code") is adapter
    assert registry.list_adapters() == (adapter,)


def test_register_duplicate_adapter_name_raises():
    registry.register_adapter(ClaudeCodeAdapter())

    with pytest.raises(ValueError, match="adapter already registered"):
        registry.register_adapter(ClaudeCodeAdapter())


def test_get_unknown_adapter_raises_key_error():
    with pytest.raises(KeyError):
        registry.get_adapter("unknown")


def test_register_builtin_adapters_registers_claude_code():
    register_builtin_adapters()

    assert registry.get_adapter("claude-code").name == "claude-code"
    assert registry.get_adapter("cursor").name == "cursor"
    assert tuple(adapter.name for adapter in registry.list_adapters()) == (
        "claude-code",
        "cursor",
    )


def test_register_and_get_cursor_adapter():
    adapter = CursorAdapter()

    registry.register_adapter(adapter)

    assert registry.get_adapter("cursor") is adapter
