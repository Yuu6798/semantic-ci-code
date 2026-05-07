from __future__ import annotations

from semantic_ci_code.repair_compiler.core import RepairCompiler
from semantic_ci_code.repair_compiler.types import (
    Adapter,
    CompiledPreGen,
    CompiledRepair,
)

__all__ = [
    "Adapter",
    "CompiledPreGen",
    "CompiledRepair",
    "RepairCompiler",
    "get_adapter",
    "list_adapters",
    "register_adapter",
]

_ADAPTERS: dict[str, Adapter] = {}


def register_adapter(adapter: Adapter) -> None:
    if adapter.name in _ADAPTERS:
        raise ValueError(f"adapter already registered: {adapter.name}")
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: str) -> Adapter:
    return _ADAPTERS[name]


def list_adapters() -> tuple[Adapter, ...]:
    return tuple(_ADAPTERS[name] for name in sorted(_ADAPTERS))
