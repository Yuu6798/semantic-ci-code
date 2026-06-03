from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from semantic_ci_code.compiler import (
    CompiledAPISurfaceAllowRule,
    CompiledAuthorship,
    CompiledConstraint,
    CompiledEffectAllowRule,
    CompiledTarget,
)
from semantic_ci_code.domain.state_schema import CodeState, LocDelta
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict
from semantic_ci_code.evaluator.operators import CanonicalMapping
from semantic_ci_code.repair import RepairCategory, RepairInstruction, RepairPlan

SCHEMA_VERSION = "6"
PACKAGE_NAME = "semantic-ci-code"
UNKNOWN_VERSION = "0.0.0+unknown"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_payload(
    subcommand: str,
    *,
    state: CodeState | None = None,
    compiled: CompiledTarget | None = None,
    verdict: Verdict | None = None,
    repair_plan: RepairPlan | None = None,
    files_touched: int = 0,
    loc_delta: LocDelta | None = None,
    mode: str | None = None,
    cache_stats: Any | None = None,
    baseline_source: str | None = None,
    baseline_rev: str | None = None,
    candidate_source: str | None = None,
    candidate_rev: str | None = None,
    timed_out_dimensions: frozenset[str] | tuple[str, ...] | list[str] | None = None,
    security_verdict: str | None = None,
    security_as_of: str | None = None,
    security_detail: Any | None = None,
    suite_verdict: str | None = None,
) -> dict[str, Any]:
    engine = _engine_payload(
        baseline_source=baseline_source,
        baseline_rev=baseline_rev,
        candidate_source=candidate_source,
        candidate_rev=candidate_rev,
        timed_out_dimensions=timed_out_dimensions,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "subcommand": subcommand,
        "mode": mode,
        "verdict": verdict.result.value if verdict is not None else None,
    }
    if security_detail is not None:
        payload["security"] = _serialize_security_detail(security_detail)
    elif security_verdict is not None:
        payload["security"] = {"verdict": security_verdict, "as_of": security_as_of}
    if suite_verdict is not None:
        payload["suite_verdict"] = suite_verdict
    payload.update(
        {
            "intent": compiled.intent if compiled is not None else None,
            "primary_kind": compiled.primary_kind.value if compiled is not None else None,
            "allowed_secondary_kinds": (
                [kind.value for kind in compiled.allowed_secondary_kinds]
                if compiled is not None
                else []
            ),
            "target_authorship": (
                _serialize_authorship(compiled.authorship)
                if compiled is not None and compiled.authorship is not None
                else None
            ),
            "summary": _summary(verdict, repair_plan) if verdict is not None else None,
            "results": (
                [_serialize_constraint_result(result) for result in verdict.results]
                if verdict is not None
                else []
            ),
            "repair_plan": (
                _serialize_repair_plan(repair_plan) if repair_plan is not None else None
            ),
            "code_state": state.model_dump(mode="json") if state is not None else None,
            "files_touched": files_touched,
            "loc_delta": _serialize_loc_delta(loc_delta or LocDelta()),
            "cache": _serialize_cache_stats(cache_stats),
            "engine": engine,
        }
    )
    return payload


def build_observe_payload(state: CodeState) -> dict[str, Any]:
    return build_payload("observe", state=state)


def build_compile_payload(
    compiled: CompiledTarget,
    *,
    cache_stats: Any | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "subcommand": "compile",
        "compiled_target": {
            "intent": compiled.intent,
            "primary_kind": compiled.primary_kind.value,
            "allowed_secondary_kinds": [kind.value for kind in compiled.allowed_secondary_kinds],
            "scope": [[key, list(values)] for key, values in compiled.scope],
            "authorship": _serialize_authorship(compiled.authorship),
            "api_surface_policy": {
                "allow_changes": [
                    _serialize_api_surface_allow_rule(rule)
                    for rule in compiled.api_surface_allow_changes
                ],
            },
            "effects_policy": {
                "allow_new": [
                    _serialize_effect_allow_rule(rule) for rule in compiled.effect_allow_new
                ],
            },
            "constraints": [
                _serialize_compiled_constraint(constraint) for constraint in compiled.constraints
            ],
        },
        "cache": _serialize_cache_stats(cache_stats),
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _engine_payload(
    *,
    baseline_source: str | None = None,
    baseline_rev: str | None = None,
    candidate_source: str | None = None,
    candidate_rev: str | None = None,
    timed_out_dimensions: frozenset[str] | tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    engine: dict[str, Any] = {}
    if baseline_source is not None or baseline_rev is not None:
        engine["baseline"] = {"source": baseline_source, "rev": baseline_rev}
    if candidate_source is not None or candidate_rev is not None:
        engine["candidate"] = {"source": candidate_source, "rev": candidate_rev}
    if timed_out_dimensions:
        engine["timed_out_dimensions"] = sorted(timed_out_dimensions)
    engine["extractor_pyver"] = f"{sys.version_info.major}.{sys.version_info.minor}"
    engine["package_version"] = package_version()
    return engine


def _summary(verdict: Verdict, repair_plan: RepairPlan | None) -> dict[str, int]:
    instructions = repair_plan.instructions if repair_plan is not None else ()
    return {
        "fix_required": sum(
            1 for item in instructions if item.category is RepairCategory.FIX_REQUIRED
        ),
        "suggested": sum(1 for item in instructions if item.category is RepairCategory.SUGGESTED),
        "info": sum(1 for item in instructions if item.category is RepairCategory.INFO),
        "unresolved": sum(
            1
            for item in instructions
            if item.category is RepairCategory.UNRESOLVED
            and item.status is not ResultStatus.SKIPPED
        ),
        "satisfied": sum(1 for item in verdict.results if item.status is ResultStatus.SATISFIED),
        "skipped": sum(1 for item in verdict.results if item.status is ResultStatus.SKIPPED),
    }


def _serialize_constraint_result(result: ConstraintResult) -> dict[str, Any]:
    return {
        "constraint_id": result.constraint_id,
        "source": result.source.value,
        "kind": result.kind.value,
        "target": result.target,
        "operator": result.operator.value,
        "severity": result.severity.value,
        "unknown_policy": result.unknown_policy.value,
        "tolerance": result.tolerance,
        "evidence_required": result.evidence_required,
        "status": result.status.value,
        "error_code": result.error_code,
        "unknown_cause": result.unknown_cause.value if result.unknown_cause else None,
        "evidence": _pairs_to_dict(result.evidence),
    }


def _serialize_compiled_constraint(constraint: CompiledConstraint) -> dict[str, Any]:
    return {
        "id": constraint.id,
        "source": constraint.source.value,
        "kind": constraint.kind.value,
        "target": constraint.target,
        "operator": constraint.operator.value,
        "expected": _json_value(constraint.expected),
        "severity": constraint.severity.value,
        "unknown_policy": constraint.unknown_policy.value,
        "tolerance": constraint.tolerance,
        "evidence_required": constraint.evidence_required,
        "scope": _json_value(constraint.scope),
    }


def _serialize_api_surface_allow_rule(rule: CompiledAPISurfaceAllowRule) -> dict[str, Any]:
    return {
        "fqn": rule.fqn,
        "fqn_prefix": rule.fqn_prefix,
    }


def _serialize_effect_allow_rule(rule: CompiledEffectAllowRule) -> dict[str, Any]:
    return {
        "fqn": rule.fqn,
        "effect_class": rule.effect_class.value if rule.effect_class is not None else None,
    }


def _serialize_authorship(authorship: CompiledAuthorship | None) -> dict[str, Any] | None:
    if authorship is None:
        return None
    return {
        "authors": [
            {
                "identity": author.identity,
                "signature": author.signature,
            }
            for author in authorship.authors
        ],
        "declared_at": authorship.declared_at,
        "generation_metadata": _json_value(authorship.generation_metadata),
    }


def _serialize_repair_plan(plan: RepairPlan) -> dict[str, Any]:
    return {
        "result": plan.result.value,
        "instructions": [
            _serialize_repair_instruction(instruction) for instruction in plan.instructions
        ],
    }


def _serialize_repair_instruction(instruction: RepairInstruction) -> dict[str, Any]:
    return {
        "constraint_id": instruction.constraint_id,
        "source": instruction.source.value,
        "kind": instruction.kind.value,
        "target": instruction.target,
        "operator": instruction.operator.value,
        "severity": instruction.severity.value,
        "unknown_policy": instruction.unknown_policy.value,
        "status": instruction.status.value,
        "error_code": instruction.error_code,
        "unknown_cause": instruction.unknown_cause.value if instruction.unknown_cause else None,
        "repair_code": instruction.repair_code,
        "category": instruction.category.value,
        "message": instruction.message,
        "observed": _json_canonical_value(instruction.observed),
        "expected": _json_canonical_value(instruction.expected),
        "added": [_json_canonical_value(item) for item in instruction.added],
        "removed": [_json_canonical_value(item) for item in instruction.removed],
        "missing": [_json_canonical_value(item) for item in instruction.missing],
        "extra": [_json_canonical_value(item) for item in instruction.extra],
        "extra_evidence": _pairs_to_dict(instruction.extra_evidence),
    }


def _serialize_loc_delta(loc_delta: LocDelta) -> dict[str, int]:
    return {"added": loc_delta.added, "removed": loc_delta.removed}


def _serialize_cache_stats(stats: Any | None) -> dict[str, Any]:
    if stats is None:
        return {
            "hit": 0,
            "miss": 0,
            "invalid": 0,
            "write_failed": 0,
            "disabled": True,
        }
    return {
        "hit": int(getattr(stats, "hit", 0)),
        "miss": int(getattr(stats, "miss", 0)),
        "invalid": int(getattr(stats, "invalid", 0)),
        "write_failed": int(getattr(stats, "write_failed", 0)),
        "disabled": bool(getattr(stats, "disabled", False)),
    }


def _serialize_security_detail(detail: Any) -> dict[str, Any]:
    return {
        "verdict": detail.status,
        "as_of": detail.as_of.isoformat(),
        "global_count_violated": bool(detail.global_count_violated),
        "sensors": [
            {
                "sensor_id": sensor.sensor_id,
                "status": sensor.status,
                "added": [_serialize_security_finding(finding) for finding in sensor.added],
                "removed": [_serialize_security_finding(finding) for finding in sensor.removed],
                "suppressed": [
                    _serialize_security_finding(finding) for finding in sensor.suppressed
                ],
                "drift_reason": sensor.drift_reason,
                "unchanged_count": sensor.unchanged_count,
            }
            for sensor in detail.sensors
        ],
    }


def _serialize_security_finding(finding: Any) -> dict[str, Any]:
    return finding.model_dump(mode="json")


def _pairs_to_dict(pairs: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
    return {key: _json_canonical_value(value) for key, value in pairs}


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _json_canonical_value(value: Any) -> Any:
    if isinstance(value, CanonicalMapping):
        return {str(key): _json_canonical_value(item) for key, item in value}
    if isinstance(value, tuple | list):
        return [_json_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_canonical_value(item) for key, item in value.items()}
    return value
