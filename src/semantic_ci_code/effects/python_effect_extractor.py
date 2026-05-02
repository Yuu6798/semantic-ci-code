from __future__ import annotations

import ast
from functools import lru_cache
from importlib import resources

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

DEFAULT_DB_PACKAGE = "semantic_ci_code.effects"
DEFAULT_DB_RESOURCE_NAME = "effect_db_python.yaml"
PYTHON_LANGUAGE = "python"


@lru_cache(maxsize=1)
def default_python_effect_db() -> tuple[EffectSignature, ...]:
    """Return the project-default Python effect signature database.

    The YAML is shipped as package data so resolution works identically
    in editable installs, plain wheels, and zipped distributions.
    """
    resource = resources.files(DEFAULT_DB_PACKAGE).joinpath(DEFAULT_DB_RESOURCE_NAME)
    with resources.as_file(resource) as path:
        return load_effect_db(path)


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
    """Build a call-name → signature lookup, restricted to Python entries.

    A shared multi-language DB may declare a non-Python signature for
    a call name that also exists in Python (e.g. ``print``). Filtering
    by ``language`` here keeps the Python extractor from picking up
    foreign entries just because they were declared first.
    """
    index: dict[str, EffectSignature] = {}
    for signature in signatures:
        if signature.language != PYTHON_LANGUAGE:
            continue
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
