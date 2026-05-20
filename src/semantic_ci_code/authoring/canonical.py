"""Canonical syntactic forms accepted by the Brief 8 authoring layer.

Single source of truth for the identifier shapes that ``init --recipe
--from-*``, the Markdown PR / issue parsers, and any future Brief 8
authoring surface (e.g. ``target-catalog``) admit as user-declared
values. Each predicate mirrors the shape an extractor or evaluator
already produces / consumes, so the authoring layer never accepts a
value the downstream pipeline would silently fail to match.

Producer references — keep these in sync if the producer side moves:

- ``is_canonical_fqn`` mirrors entries the api-surface extractor emits
  into ``CodeState.api_surface.added`` (and the matching ``removed`` /
  ``changed`` deltas in ``CodeStateDelta``): dotted Python paths shaped
  ``module.symbol`` or ``module.Class.method``, identifier segments
  only, never containing ``::``.
- ``is_canonical_fqn_prefix`` mirrors the prefix the evaluator passes to
  ``fqn.startswith(rule.fqn_prefix)`` for the
  ``api_surface.allow_changes`` policy hatch. The trailing ``.`` is
  required so ``"legacy."`` cannot accidentally permit ``"legacy2.Foo"``
  through ``startswith``; ``"pkg.."`` is rejected so a doubled trailing
  dot never produces a prefix that real extractor FQNs cannot satisfy.
- ``is_canonical_test_id`` mirrors ``code_state_delta._test_case_id``,
  which joins ``test_file::test_function`` where ``test_file`` is
  ``resolved.relative_to(root).as_posix()`` (relative POSIX path with
  ``.py`` suffix and no ``.`` / ``..`` / empty segments) and
  ``test_function`` is either ``test_*`` or ``Test*::test_*`` — the only
  shapes ``python_test_surface_extractor`` emits.
"""

from __future__ import annotations

__all__ = [
    "is_canonical_fqn",
    "is_canonical_fqn_prefix",
    "is_canonical_test_id",
]


def is_canonical_fqn(value: str) -> bool:
    if not value or "::" in value or "." not in value:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    return all(part.isidentifier() for part in value.split("."))


def is_canonical_fqn_prefix(value: str) -> bool:
    if not value or "::" in value or not value.endswith(".") or value.startswith("."):
        return False
    body = value[:-1]
    return bool(body) and all(part.isidentifier() for part in body.split("."))


def is_canonical_test_id(value: str) -> bool:
    path, sep, name = value.partition("::")
    if not sep or not path or not name or " " in path or " " in name:
        return False
    if "\\" in path or path.startswith("/") or not path.endswith(".py"):
        return False
    if any(seg in ("", ".", "..") for seg in path.split("/")):
        return False
    parts = name.split("::")
    if not all(part.isidentifier() for part in parts):
        return False
    if len(parts) == 1:
        return parts[0].startswith("test_")
    if len(parts) == 2:
        return parts[0].startswith("Test") and parts[1].startswith("test_")
    return False
