"""Deterministic advisory re-projection for LLM scout findings.

This module is advisory-only and never participates in verdict computation.
LLM scouts run once on candidate code; these helpers re-project candidate
anchors onto baseline CodeState using deterministic predicates. When a
predicate cannot prove the vulnerability was already present, the finding is
kept as added to preserve the D7 recall-first policy.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState, RenameEntry
from semantic_ci_code.sensor.models import LLMSecurityFinding


@dataclass(frozen=True)
class AdvisoryReprojection:
    """Advisory-only LLM finding split after baseline re-projection."""

    added: tuple[LLMSecurityFinding, ...]
    pre_existing: tuple[LLMSecurityFinding, ...]


# Heuristic, advisory-only, recall-first table. These names are decorator leaves:
# `auth.login_required` and `@auth.login_required(...)` both compare as `login_required`.
_ABSENCE_GUARD_DECORATORS: Mapping[str, frozenset[str]] = {
    "missing-authz": frozenset(
        {
            "authenticated",
            "login_required",
            "permission_required",
            "requires_auth",
        }
    ),
}


def compute_advisory_reprojection(
    candidate_findings: Iterable[LLMSecurityFinding],
    baseline_code: CodeState,
    *,
    renames: tuple[RenameEntry, ...] = (),
) -> AdvisoryReprojection:
    """Classify one-run candidate LLM findings as added or pre-existing.

    The baseline input is intentionally CodeState only. This makes a two-run
    LLM diff impossible at the function boundary: baseline LLM findings are
    never accepted, and unresolved predicates fall back to `added`.
    """

    baseline_by_fqn = {entry.fqn: entry for entry in baseline_code.api_surface}
    rename_old_by_new = {
        _posix_path(rename.new_path): _posix_path(rename.old_path) for rename in renames
    }
    added: list[LLMSecurityFinding] = []
    pre_existing: list[LLMSecurityFinding] = []
    for finding in candidate_findings:
        if _already_in_baseline(
            finding,
            baseline_by_fqn=baseline_by_fqn,
            rename_old_by_new=rename_old_by_new,
        ):
            pre_existing.append(finding)
        else:
            added.append(finding)

    return AdvisoryReprojection(
        added=_sort_findings(added),
        pre_existing=_sort_findings(pre_existing),
    )


def _already_in_baseline(
    finding: LLMSecurityFinding,
    *,
    baseline_by_fqn: Mapping[str, APISurfaceEntry],
    rename_old_by_new: Mapping[str, str],
) -> bool:
    if finding.anchor_kind == "presence":
        return False

    guard_decorators = _ABSENCE_GUARD_DECORATORS.get(finding.finding_class)
    if guard_decorators is None:
        return False

    baseline_site = _resolve_baseline_site(
        finding,
        baseline_by_fqn=baseline_by_fqn,
        rename_old_by_new=rename_old_by_new,
    )
    if baseline_site is None:
        return False
    return not _has_guard_decorator(baseline_site, guard_decorators)


def _resolve_baseline_site(
    finding: LLMSecurityFinding,
    *,
    baseline_by_fqn: Mapping[str, APISurfaceEntry],
    rename_old_by_new: Mapping[str, str],
) -> APISurfaceEntry | None:
    direct = baseline_by_fqn.get(finding.qualified_name)
    if direct is not None:
        return direct

    old_path = rename_old_by_new.get(_posix_path(finding.module_path))
    if old_path is None:
        return None
    candidate_module = _module_name_from_path(finding.module_path)
    baseline_module = _module_name_from_path(old_path)
    if finding.qualified_name == candidate_module:
        baseline_fqn = baseline_module
    elif finding.qualified_name.startswith(candidate_module + "."):
        baseline_fqn = baseline_module + finding.qualified_name[len(candidate_module) :]
    else:
        return None
    return baseline_by_fqn.get(baseline_fqn)


def _has_guard_decorator(
    entry: APISurfaceEntry,
    guard_decorators: frozenset[str],
) -> bool:
    return any(_decorator_leaf(decorator) in guard_decorators for decorator in entry.decorators)


def _decorator_leaf(decorator: str) -> str:
    return decorator.rsplit(".", 1)[-1]


def _module_name_from_path(path: str) -> str:
    normalized = _posix_path(path).removeprefix("./")
    if normalized.endswith("/__init__.py"):
        normalized = normalized[: -len("/__init__.py")]
    elif normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.replace("/", ".")


def _posix_path(path: str) -> str:
    return path.replace("\\", "/")


def _sort_findings(findings: Iterable[LLMSecurityFinding]) -> tuple[LLMSecurityFinding, ...]:
    return tuple(sorted(findings, key=lambda finding: finding.canonical_id))
