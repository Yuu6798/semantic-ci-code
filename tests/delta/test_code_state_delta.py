from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    CFGDelta,
    CodeState,
    CodeStateDelta,
    ComplexityDelta,
    ComplexityEntry,
    EffectChanges,
    EffectClass,
    EffectEntry,
    ImportDelta,
    ImportEntry,
    LocDelta,
    ModuleGraphEntry,
    SymbolDelta,
)
from semantic_ci_code.domain.state_schema import (
    TestSurfaceDelta as SurfaceDelta,
)
from semantic_ci_code.domain.state_schema import (
    TestSurfaceEntry as SurfaceEntry,
)
from semantic_ci_code.pipeline import extract_python_code_state

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "delta"
BASELINE_PKG = FIXTURE_ROOT / "baseline_pkg"
CANDIDATE_PKG = FIXTURE_ROOT / "candidate_pkg"


def api(
    fqn: str,
    *,
    kind: str = "function",
    signature: str | None = "def f():\n    ...",
    visibility: str | None = "public",
    decorators: tuple[str, ...] = (),
) -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind=kind,
        signature=signature,
        visibility=visibility,
        decorators=decorators,
    )


def api_delta_record(entry: APISurfaceEntry) -> dict[str, object]:
    dumped = entry.model_dump(mode="json")
    dumped.pop("decorators", None)
    return dumped


def effect(
    fqn: str,
    effect_class: EffectClass,
    *,
    resolved_call: str | None = None,
) -> EffectEntry:
    evidence = {"resolved_call": resolved_call} if resolved_call is not None else None
    return EffectEntry(
        fqn=fqn,
        effect_class=effect_class,
        confidence=1.0,
        evidence=evidence,
    )


def imp(
    module: str,
    *,
    from_: str | None = None,
    symbols: tuple[str, ...] = (),
) -> ImportEntry:
    return ImportEntry(module=module, from_=from_, symbols=symbols)


def cx(
    fqn: str,
    cyclomatic: int | None,
    cognitive: int | None,
) -> ComplexityEntry:
    return ComplexityEntry(fqn=fqn, cyclomatic=cyclomatic, cognitive=cognitive)


def surface_entry(
    test_file: str,
    test_function: str,
    *,
    asserts: int | None = 1,
    parametrize_count: int | None = None,
) -> SurfaceEntry:
    return SurfaceEntry(
        test_file=test_file,
        test_function=test_function,
        asserts=asserts,
        parametrize_count=parametrize_count,
    )


def graph(module: str, imports: tuple[str, ...] = ()) -> ModuleGraphEntry:
    return ModuleGraphEntry(module=module, imports=imports)


def test_identical_state_returns_empty_delta():
    state = CodeState(
        api_surface=(api("pkg.same"),),
        effects=(effect("print", EffectClass.STDOUT),),
        imports=(imp("os"),),
        complexity=(cx("pkg.same", 1, 0),),
        test_surface=(surface_entry("tests/test_same.py", "test_same"),),
        module_graph=(graph("pkg"),),
    )

    delta = compute_code_state_delta(state, state)

    assert delta == CodeStateDelta()
    assert delta.python_specific is None
    assert delta.coverage_delta is None
    assert delta.type_changes == ()


def test_api_surface_added_removed_and_changed_entries():
    baseline = CodeState(
        api_surface=(
            api("pkg.removed"),
            api("pkg.removed_decorated", decorators=("login_required",)),
            api("pkg.changed_sig", signature="def changed_sig(x: int):\n    ..."),
            api("pkg.changed_visibility", visibility="public", decorators=("login_required",)),
        )
    )
    candidate = CodeState(
        api_surface=(
            api("pkg.added", decorators=("login_required",)),
            api("pkg.changed_sig", signature="def changed_sig(x: str):\n    ..."),
            api("pkg.changed_visibility", visibility="private", decorators=("requires_auth",)),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.api_surface_delta.added == (
        api_delta_record(api("pkg.added", decorators=("login_required",))),
    )
    assert delta.api_surface_delta.removed == (
        api_delta_record(api("pkg.removed")),
        api_delta_record(api("pkg.removed_decorated", decorators=("login_required",))),
    )
    assert delta.api_surface_delta.changed == (
        {
            "fqn": "pkg.changed_sig",
            "kind": "function",
            "before": api_delta_record(
                api(
                    "pkg.changed_sig",
                    signature="def changed_sig(x: int):\n    ...",
                )
            ),
            "after": api_delta_record(
                api(
                    "pkg.changed_sig",
                    signature="def changed_sig(x: str):\n    ...",
                )
            ),
        },
        {
            "fqn": "pkg.changed_visibility",
            "kind": "function",
            "before": api_delta_record(
                api("pkg.changed_visibility", visibility="public", decorators=("login_required",))
            ),
            "after": api_delta_record(
                api("pkg.changed_visibility", visibility="private", decorators=("requires_auth",))
            ),
        },
    )
    assert all("decorators" not in item for item in delta.api_surface_delta.added)
    assert all("decorators" not in item for item in delta.api_surface_delta.removed)
    assert all(
        "decorators" not in payload
        for change in delta.api_surface_delta.changed
        for payload in (change["before"], change["after"])
    )
    assert delta.decorators_delta.added == (
        {"fqn": "pkg.added", "decorator": "login_required", "decorator_leaf": "login_required"},
    )
    assert delta.decorators_delta.removed == (
        {
            "fqn": "pkg.changed_visibility",
            "decorator": "login_required",
            "decorator_leaf": "login_required",
        },
        {
            "fqn": "pkg.removed_decorated",
            "decorator": "login_required",
            "decorator_leaf": "login_required",
        },
    )


def test_decorator_changes_are_recorded_without_api_surface_change():
    baseline = CodeState(
        api_surface=(
            api("pkg.view", decorators=("auth.login_required", "app.route")),
            api("pkg._internal", visibility="private", decorators=("login_required",)),
        )
    )
    candidate = CodeState(
        api_surface=(
            api("pkg.view", decorators=("app.route",)),
            api("pkg._internal", visibility="private"),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.api_surface_delta == SymbolDelta()
    assert delta.decorators_delta == SymbolDelta(
        removed=(
            {
                "fqn": "pkg.view",
                "decorator": "auth.login_required",
                "decorator_leaf": "login_required",
            },
        )
    )


def test_decorator_delta_records_added_and_removed_in_sorted_order():
    baseline = CodeState(
        api_surface=(
            api("pkg.b", decorators=("requires_auth",)),
            api("pkg.a", decorators=("login_required",)),
        )
    )
    candidate = CodeState(
        api_surface=(
            api("pkg.b", decorators=("permission_required",)),
            api("pkg.a", decorators=("login_required", "requires_auth")),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.decorators_delta.added == (
        {"fqn": "pkg.a", "decorator": "requires_auth", "decorator_leaf": "requires_auth"},
        {
            "fqn": "pkg.b",
            "decorator": "permission_required",
            "decorator_leaf": "permission_required",
        },
    )
    assert delta.decorators_delta.removed == (
        {"fqn": "pkg.b", "decorator": "requires_auth", "decorator_leaf": "requires_auth"},
    )
    assert delta.decorators_delta.changed == ()


def test_api_surface_duplicate_identity_keys_are_group_compared():
    overload_int = api("pkg.parse", signature="@overload\ndef parse(value: int):\n    ...")
    overload_str = api("pkg.parse", signature="@overload\ndef parse(value: str):\n    ...")
    overload_bytes = api("pkg.parse", signature="@overload\ndef parse(value: bytes):\n    ...")
    baseline = CodeState(api_surface=(overload_str, overload_int))
    candidate = CodeState(api_surface=(overload_int, overload_bytes))

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.api_surface_delta.added == ()
    assert delta.api_surface_delta.removed == ()
    assert delta.api_surface_delta.changed == (
        {
            "fqn": "pkg.parse",
            "kind": "function",
            "before": [
                api_delta_record(overload_int),
                api_delta_record(overload_str),
            ],
            "after": [
                api_delta_record(overload_bytes),
                api_delta_record(overload_int),
            ],
        },
    )


def test_effects_added_removed_and_class_change_as_removed_plus_added():
    baseline = CodeState(
        effects=(
            effect("os.remove", EffectClass.FS),
            effect("pkg.op", EffectClass.IO),
        )
    )
    candidate = CodeState(
        effects=(
            effect("pkg.op", EffectClass.FS),
            effect("subprocess.run", EffectClass.PROCESS),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.effect_changes.added == (
        effect("pkg.op", EffectClass.FS).model_dump(mode="json"),
        effect("subprocess.run", EffectClass.PROCESS).model_dump(mode="json"),
    )
    assert delta.effect_changes.removed == (
        effect("os.remove", EffectClass.FS).model_dump(mode="json"),
        effect("pkg.op", EffectClass.IO).model_dump(mode="json"),
    )


def test_effects_same_scope_and_class_keep_resolved_call_identity():
    baseline = CodeState(effects=(effect("pkg.run", EffectClass.FS, resolved_call="open"),))
    candidate = CodeState(
        effects=(
            effect("pkg.run", EffectClass.FS, resolved_call="open"),
            effect("pkg.run", EffectClass.FS, resolved_call="os.remove"),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.effect_changes.added == (
        effect("pkg.run", EffectClass.FS, resolved_call="os.remove").model_dump(mode="json"),
    )
    assert delta.effect_changes.removed == ()


def test_imports_added_removed_and_symbol_change_as_removed_plus_added():
    baseline = CodeState(
        imports=(
            imp("json"),
            imp("os", symbols=("path",)),
            imp("pkg", from_=".", symbols=("old",)),
        )
    )
    candidate = CodeState(
        imports=(
            imp("os", symbols=("sep",)),
            imp("pkg", from_=".", symbols=("new",)),
            imp("sys"),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.imports_delta.added == (
        imp("os", symbols=("sep",)).model_dump(mode="json", by_alias=True),
        imp("pkg", from_=".", symbols=("new",)).model_dump(mode="json", by_alias=True),
        imp("sys").model_dump(mode="json", by_alias=True),
    )
    assert delta.imports_delta.removed == (
        imp("json").model_dump(mode="json", by_alias=True),
        imp("os", symbols=("path",)).model_dump(mode="json", by_alias=True),
        imp("pkg", from_=".", symbols=("old",)).model_dump(mode="json", by_alias=True),
    )
    assert "from" in delta.imports_delta.added[1]


def test_complexity_delta_is_net_total_and_none_counts_as_zero():
    baseline = CodeState(complexity=(cx("pkg.a", 5, 1), cx("pkg.none", None, None)))
    candidate = CodeState(complexity=(cx("pkg.a", 2, 4), cx("pkg.none", 3, None)))

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.complexity_delta == ComplexityDelta(cyclomatic=0, cognitive=3)


def test_complexity_per_function_detail_goes_to_python_specific():
    baseline = CodeState(complexity=(cx("pkg.removed", 5, 5), cx("pkg.changed", 1, 1)))
    candidate = CodeState(complexity=(cx("pkg.added", 2, 3), cx("pkg.changed", 2, 1)))

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.python_specific == {
        "complexity_changes": {
            "added": [cx("pkg.added", 2, 3).model_dump(mode="json")],
            "removed": [cx("pkg.removed", 5, 5).model_dump(mode="json")],
            "changed": [
                {
                    "fqn": "pkg.changed",
                    "before": cx("pkg.changed", 1, 1).model_dump(mode="json"),
                    "after": cx("pkg.changed", 2, 1).model_dump(mode="json"),
                }
            ],
        }
    }


def test_test_surface_delta_new_files_new_cases_and_removed_cases():
    baseline = CodeState(
        test_surface=(
            surface_entry("tests/test_common.py", "test_removed"),
            surface_entry("tests/test_old.py", "test_old"),
        )
    )
    candidate = CodeState(
        test_surface=(
            surface_entry("tests/test_common.py", "test_added"),
            surface_entry("tests/test_new.py", "test_new"),
        )
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.test_surface_delta == SurfaceDelta(
        new_files=("tests/test_new.py",),
        new_cases=(
            "tests/test_common.py::test_added",
            "tests/test_new.py::test_new",
        ),
        removed_cases=(
            "tests/test_common.py::test_removed",
            "tests/test_old.py::test_old",
        ),
    )


def test_test_surface_parametrize_change_goes_to_python_specific():
    baseline = CodeState(
        test_surface=(surface_entry("tests/test_param.py", "test_value", parametrize_count=2),)
    )
    candidate = CodeState(
        test_surface=(surface_entry("tests/test_param.py", "test_value", parametrize_count=3),)
    )

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.python_specific == {
        "test_surface_changes": {
            "changed": [
                {
                    "test_file": "tests/test_param.py",
                    "test_function": "test_value",
                    "before": surface_entry(
                        "tests/test_param.py",
                        "test_value",
                        parametrize_count=2,
                    ).model_dump(mode="json"),
                    "after": surface_entry(
                        "tests/test_param.py",
                        "test_value",
                        parametrize_count=3,
                    ).model_dump(mode="json"),
                }
            ]
        }
    }


def test_module_graph_delta_goes_to_python_specific():
    baseline = CodeState(module_graph=(graph("alpha", ("beta",)), graph("beta")))
    candidate = CodeState(module_graph=(graph("alpha", ("gamma",)), graph("gamma")))

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.python_specific == {
        "module_graph_delta": {
            "added_edges": [["alpha", "gamma"]],
            "removed_edges": [["alpha", "beta"]],
        }
    }


def test_delta_symmetry_invariant():
    baseline = CodeState(
        api_surface=(
            api("pkg.removed"),
            api("pkg.changed", signature="old"),
        ),
        effects=(effect("pkg.old_effect", EffectClass.IO),),
        imports=(imp("old_mod"),),
        complexity=(
            cx("pkg.removed", 3, 1),
            cx("pkg.changed", 1, 1),
        ),
        test_surface=(
            surface_entry("tests/test_common.py", "test_removed"),
            surface_entry("tests/test_common.py", "test_changed", parametrize_count=2),
        ),
        module_graph=(graph("pkg.a", ("pkg.b",)),),
    )
    candidate = CodeState(
        api_surface=(
            api("pkg.added"),
            api("pkg.changed", signature="new"),
        ),
        effects=(effect("pkg.new_effect", EffectClass.FS),),
        imports=(imp("new_mod"),),
        complexity=(
            cx("pkg.added", 2, 2),
            cx("pkg.changed", 4, 1),
        ),
        test_surface=(
            surface_entry("tests/test_common.py", "test_added"),
            surface_entry("tests/test_common.py", "test_changed", parametrize_count=3),
        ),
        module_graph=(graph("pkg.a", ("pkg.c",)),),
    )

    forward = compute_code_state_delta(baseline, candidate)
    reverse = compute_code_state_delta(candidate, baseline)

    assert list(forward.python_specific or {}) == [
        "module_graph_delta",
        "complexity_changes",
        "test_surface_changes",
    ]
    assert reverse == _flip_delta(forward)


def test_model_dump_json_is_byte_identical_same_process():
    baseline = CodeState(api_surface=(api("pkg.old"),), imports=(imp("os"),))
    candidate = CodeState(api_surface=(api("pkg.new"),), imports=(imp("sys"),))

    first = compute_code_state_delta(baseline, candidate)
    second = compute_code_state_delta(baseline, candidate)

    assert first.model_dump_json() == second.model_dump_json()


def test_model_dump_json_is_byte_identical_across_subprocess_invocations():
    script = """
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState
baseline = CodeState(api_surface=(APISurfaceEntry(fqn="pkg.old", kind="function"),))
candidate = CodeState(api_surface=(APISurfaceEntry(fqn="pkg.new", kind="function"),))
print(compute_code_state_delta(baseline, candidate).model_dump_json())
"""
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else os.pathsep.join((src_path, env["PYTHONPATH"]))
    )
    run1 = _run_subprocess(script, env=env, pythonhashseed="1")
    run2 = _run_subprocess(script, env=env, pythonhashseed="2")

    assert run1.stdout == run2.stdout


def test_hand_built_virtual_code_state_engine_contract():
    baseline = CodeState(api_surface=(api("virtual.old"),))
    candidate = CodeState(api_surface=(api("virtual.new"),))

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.api_surface_delta.added == (api_delta_record(api("virtual.new")),)
    assert delta.api_surface_delta.removed == (api_delta_record(api("virtual.old")),)


def test_p1_unimplemented_fields_stay_at_defaults():
    delta = compute_code_state_delta(CodeState(), CodeState(api_surface=(api("pkg.added"),)))

    assert delta.type_changes == ()
    assert delta.cfg_delta == CFGDelta()
    assert delta.coverage_delta is None
    assert delta.files_touched == 0
    assert delta.loc_delta == LocDelta()
    assert delta.renames == ()
    assert delta.typescript_specific is None


def test_csci_10_integration_from_extracted_code_states():
    baseline = extract_python_code_state(BASELINE_PKG)
    candidate = extract_python_code_state(CANDIDATE_PKG)

    delta = compute_code_state_delta(baseline, candidate)

    assert delta.api_surface_delta.changed
    assert any(entry["module"] == "json" for entry in delta.imports_delta.added)
    assert delta.complexity_delta.cyclomatic > 0


def _flip_delta(delta: CodeStateDelta) -> CodeStateDelta:
    return CodeStateDelta(
        api_surface_delta=SymbolDelta(
            added=delta.api_surface_delta.removed,
            removed=delta.api_surface_delta.added,
            changed=tuple(_flip_before_after(change) for change in delta.api_surface_delta.changed),
        ),
        decorators_delta=SymbolDelta(
            added=delta.decorators_delta.removed,
            removed=delta.decorators_delta.added,
            changed=(),
        ),
        effect_changes=EffectChanges(
            added=delta.effect_changes.removed,
            removed=delta.effect_changes.added,
        ),
        imports_delta=ImportDelta(
            added=delta.imports_delta.removed,
            removed=delta.imports_delta.added,
        ),
        complexity_delta=ComplexityDelta(
            cyclomatic=-delta.complexity_delta.cyclomatic,
            cognitive=-delta.complexity_delta.cognitive,
        ),
        test_surface_delta=SurfaceDelta(
            new_files=delta.test_surface_delta.new_files,
            new_cases=delta.test_surface_delta.removed_cases,
            removed_cases=delta.test_surface_delta.new_cases,
        ),
        python_specific=_flip_python_specific(delta.python_specific),
    )


def _flip_python_specific(details: dict[str, Any] | None) -> dict[str, Any] | None:
    if details is None:
        return None

    flipped: dict[str, Any] = {}
    if "module_graph_delta" in details:
        module_graph = details["module_graph_delta"]
        flipped["module_graph_delta"] = {
            "added_edges": module_graph["removed_edges"],
            "removed_edges": module_graph["added_edges"],
        }
    if "complexity_changes" in details:
        complexity = details["complexity_changes"]
        flipped["complexity_changes"] = {
            "added": complexity["removed"],
            "removed": complexity["added"],
            "changed": [_flip_before_after(change) for change in complexity["changed"]],
        }
    if "test_surface_changes" in details:
        test_surface = details["test_surface_changes"]
        flipped["test_surface_changes"] = {
            "changed": [_flip_before_after(change) for change in test_surface["changed"]]
        }
    return flipped or None


def _flip_before_after(change: dict[str, Any]) -> dict[str, Any]:
    flipped = dict(change)
    flipped["before"] = change["after"]
    flipped["after"] = change["before"]
    return flipped


def _run_subprocess(
    script: str,
    *,
    env: dict[str, str],
    pythonhashseed: str,
) -> subprocess.CompletedProcess[str]:
    run_env = env.copy()
    run_env["PYTHONHASHSEED"] = pythonhashseed
    return subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=run_env,
        text=True,
    )
