from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from semantic_ci_code.domain.state_schema import EffectEntry
from semantic_ci_code.effects.effect_db import (
    EffectSignature,
    ResolutionLevel,
    load_effect_db,
)

# TODO(P1+): ``global_mutation`` is intentionally not represented as an
# effect_db entry. It requires statement-level detection (``global`` /
# ``nonlocal`` declarations and module-level rebindings) rather than a
# call signature, and will be implemented as a dedicated extractor pass.


def _find_default_db_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "effect_db_python.yaml"
        if candidate.is_file():
            return candidate
    msg = (
        "Default Python effect DB not found. Expected "
        "'config/effect_db_python.yaml' in a parent of "
        f"{here}."
    )
    raise FileNotFoundError(msg)


@lru_cache(maxsize=1)
def default_python_effect_db() -> tuple[EffectSignature, ...]:
    """Return the project-default Python effect signature database."""
    return load_effect_db(_find_default_db_path())


def _resolve_dotted_name(node: ast.AST) -> str | None:
    """Recover a dotted name from ``ast.Name`` / ``ast.Attribute`` chains.

    Returns ``None`` when the chain bottoms out on a non-name node (e.g.
    a call result or subscript), which signals an unresolved direct call
    in the P1 sense.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _resolve_dotted_name(node.value)
        if prefix is None:
            return None
        return f"{prefix}.{node.attr}"
    return None


def _build_call_index(
    signatures: tuple[EffectSignature, ...],
) -> dict[str, EffectSignature]:
    index: dict[str, EffectSignature] = {}
    for signature in signatures:
        index.setdefault(signature.match.call, signature)
    return index


def extract_python_effects(
    source: str,
    *,
    filename: str = "<string>",
    db: tuple[EffectSignature, ...] | None = None,
) -> tuple[EffectEntry, ...]:
    """Extract direct-call effects from Python ``source``.

    Resolution is intentionally limited to P1 ``direct_call`` semantics:
    ``ast.Name`` and chains of ``ast.Attribute`` rooted in ``ast.Name``.
    Method calls on instances and import-alias rebinds are not resolved.

    A :class:`SyntaxError` from :func:`ast.parse` propagates unchanged so
    callers can distinguish parse failures from extraction misses.
    """
    tree = ast.parse(source, filename=filename)
    signatures = db if db is not None else default_python_effect_db()
    index = _build_call_index(signatures)

    entries: list[EffectEntry] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _resolve_dotted_name(node.func)
        if dotted is None:
            continue
        signature = index.get(dotted)
        if signature is None:
            continue
        entries.append(
            EffectEntry(
                fqn=dotted,
                effect_class=signature.effect_class,
                confidence=1.0,
                evidence={
                    "call": dotted,
                    "file": filename,
                    "line": node.lineno,
                    "resolution_level": ResolutionLevel.DIRECT_CALL.value,
                },
            )
        )
    return tuple(entries)
