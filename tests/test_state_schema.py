from __future__ import annotations

from pydantic import ValidationError

from semantic_ci_code.domain.state_schema import (
    APISurfaceEntry,
    CFGDelta,
    ChangeKind,
    CodeState,
    CodeStateDelta,
    ComplexityDelta,
    ComplexityEntry,
    CoverageDelta,
    DataFlowEntry,
    EffectChanges,
    EffectClass,
    EffectEntry,
    ImportDelta,
    ImportEntry,
    LocDelta,
    ModuleGraphEntry,
    SymbolDelta,
    TypeRelation,
)
from semantic_ci_code.domain.state_schema import (
    TestSurfaceDelta as StateTestSurfaceDelta,
)
from semantic_ci_code.domain.state_schema import (
    TestSurfaceEntry as StateTestSurfaceEntry,
)


def test_change_kind_values_are_complete():
    assert {item.value for item in ChangeKind} == {
        "feature",
        "bugfix",
        "refactor",
        "test_update",
    }


def test_code_state_exposes_all_ten_dimensions_and_extensions():
    state = CodeState(
        api_surface=[
            APISurfaceEntry(
                fqn="src.api.users.fetch_user_profile",
                kind="function",
                signature="() -> UserProfile",
                visibility="public",
            )
        ],
        type_relations=[
            TypeRelation(
                fqn="src.api.users.fetch_user_profile",
                type_expr="() -> UserProfile",
                nullable=False,
            )
        ],
        effects=[EffectEntry(fqn="src.api.users.fetch_user_profile", effect_class=EffectClass.IO)],
        control_flow=[{"fqn": "src.api.users.fetch_user_profile", "cyclomatic": 2}],
        data_flow=[DataFlowEntry(source="request.user_id", sink="database.users", path=("repo",))],
        imports=[ImportEntry(module="src.api.users", from_="src.api", symbols=("UserProfile",))],
        complexity=[ComplexityEntry(fqn="src.api.users.fetch_user_profile", cyclomatic=2)],
        test_surface=[
            StateTestSurfaceEntry(
                test_file="tests/test_users.py",
                test_function="test_fetch_user_profile",
                asserts=2,
            )
        ],
        coverage=None,
        module_graph=[ModuleGraphEntry(module="src.api.users", imports=("src.models",))],
        python_specific={"decorators": ["router.get"]},
        typescript_specific=None,
    )

    dumped = state.model_dump(by_alias=True)

    assert set(dumped) == {
        "api_surface",
        "type_relations",
        "effects",
        "control_flow",
        "data_flow",
        "imports",
        "complexity",
        "test_surface",
        "coverage",
        "module_graph",
        "python_specific",
        "typescript_specific",
    }
    assert dumped["coverage"] is None
    assert dumped["imports"][0]["from"] == "src.api"


def test_code_state_delta_exposes_all_delta_fields_and_extensions():
    delta = CodeStateDelta(
        api_surface_delta=SymbolDelta(added=("src.api.users.fetch_user_profile",)),
        type_changes=({"fqn": "src.api.users.fetch_user_profile", "changed": True},),
        effect_changes=EffectChanges(added=("io",)),
        cfg_delta=CFGDelta(new_branches=1),
        imports_delta=ImportDelta(added=("src.models",)),
        complexity_delta=ComplexityDelta(cyclomatic=1, cognitive=1),
        test_surface_delta=StateTestSurfaceDelta(new_files=("tests/test_users.py",)),
        coverage_delta=CoverageDelta(line=2.5, branch=None),
        files_touched=2,
        loc_delta=LocDelta(added=40, removed=3),
        python_specific={"decorators_changed": []},
        typescript_specific=None,
    )

    dumped = delta.model_dump()

    assert set(dumped) == {
        "api_surface_delta",
        "type_changes",
        "effect_changes",
        "cfg_delta",
        "imports_delta",
        "complexity_delta",
        "test_surface_delta",
        "coverage_delta",
        "files_touched",
        "loc_delta",
        "python_specific",
        "typescript_specific",
    }
    assert delta.files_touched == 2
    assert delta.coverage_delta is not None


def test_code_state_rejects_unknown_fields():
    try:
        CodeState(unexpected_dimension=[])  # type: ignore[call-arg]
    except ValidationError as exc:
        assert "unexpected_dimension" in str(exc)
    else:
        raise AssertionError("unknown CodeState fields should be rejected")
