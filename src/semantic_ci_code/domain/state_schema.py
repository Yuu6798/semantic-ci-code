from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

JsonValue: TypeAlias = Any
JsonMapping: TypeAlias = dict[str, JsonValue]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")


class ChangeKind(StrEnum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TEST_UPDATE = "test_update"
    GENERIC = "generic"


class EffectClass(StrEnum):
    PURE = "pure"
    IO = "io"
    NET = "net"
    FS = "fs"
    PROCESS = "process"
    ENV = "env"
    TIME_RANDOM = "time_random"
    STDOUT = "stdout"
    DYNAMIC_CODE = "dynamic_code"
    UNSAFE_DESERIALIZE = "unsafe_deserialize"
    GLOBAL_MUTATION = "global_mutation"


class APISurfaceEntry(FrozenModel):
    fqn: str
    kind: str
    signature: str | None = None
    visibility: str | None = None
    decorators: tuple[str, ...] = Field(default_factory=tuple)


class TypeRelation(FrozenModel):
    fqn: str
    type_expr: str
    nullable: bool | None = None
    generic_params: tuple[str, ...] = Field(default_factory=tuple)


class EffectEntry(FrozenModel):
    fqn: str
    effect_class: EffectClass
    confidence: float | None = None
    evidence: JsonValue = None


class ControlFlowEntry(FrozenModel):
    fqn: str
    branches: int | None = None
    loops: int | None = None
    exception_paths: int | None = None
    cyclomatic: int | None = None


class DataFlowEntry(FrozenModel):
    source: str
    sink: str
    path: tuple[str, ...] = Field(default_factory=tuple)


class ImportEntry(FrozenModel):
    module: str
    from_: str | None = Field(default=None, alias="from")
    symbols: tuple[str, ...] = Field(default_factory=tuple)


class ComplexityEntry(FrozenModel):
    fqn: str
    cyclomatic: int | None = None
    cognitive: int | None = None


class TestSurfaceEntry(FrozenModel):
    test_file: str
    test_function: str
    asserts: int | None = None
    parametrize_count: int | None = None


class CoverageEntry(FrozenModel):
    file: str
    line_coverage: float
    branch_coverage: float | None = None


class ModuleGraphEntry(FrozenModel):
    module: str
    imports: tuple[str, ...] = Field(default_factory=tuple)
    imported_by: tuple[str, ...] = Field(default_factory=tuple)


class CodeState(FrozenModel):
    api_surface: tuple[APISurfaceEntry, ...] = Field(default_factory=tuple)
    type_relations: tuple[TypeRelation, ...] = Field(default_factory=tuple)
    effects: tuple[EffectEntry, ...] = Field(default_factory=tuple)
    control_flow: tuple[ControlFlowEntry, ...] = Field(default_factory=tuple)
    data_flow: tuple[DataFlowEntry, ...] = Field(default_factory=tuple)
    imports: tuple[ImportEntry, ...] = Field(default_factory=tuple)
    complexity: tuple[ComplexityEntry, ...] = Field(default_factory=tuple)
    test_surface: tuple[TestSurfaceEntry, ...] = Field(default_factory=tuple)
    coverage: tuple[CoverageEntry, ...] | None = None
    module_graph: tuple[ModuleGraphEntry, ...] = Field(default_factory=tuple)
    python_specific: JsonMapping | None = None
    typescript_specific: JsonMapping | None = None


class SymbolDelta(FrozenModel):
    added: tuple[JsonValue, ...] = Field(default_factory=tuple)
    removed: tuple[JsonValue, ...] = Field(default_factory=tuple)
    changed: tuple[JsonValue, ...] = Field(default_factory=tuple)


class EffectChanges(FrozenModel):
    added: tuple[JsonValue, ...] = Field(default_factory=tuple)
    removed: tuple[JsonValue, ...] = Field(default_factory=tuple)


class CFGDelta(FrozenModel):
    new_branches: int = 0
    removed_branches: int = 0


class ImportDelta(FrozenModel):
    added: tuple[JsonValue, ...] = Field(default_factory=tuple)
    removed: tuple[JsonValue, ...] = Field(default_factory=tuple)


class ComplexityDelta(FrozenModel):
    cyclomatic: int = 0
    cognitive: int = 0


class TestSurfaceDelta(FrozenModel):
    new_files: tuple[str, ...] = Field(default_factory=tuple)
    new_cases: tuple[str, ...] = Field(default_factory=tuple)
    removed_cases: tuple[str, ...] = Field(default_factory=tuple)


class CoverageDelta(FrozenModel):
    line: float | None = None
    branch: float | None = None


class LocDelta(FrozenModel):
    added: int = 0
    removed: int = 0


class CodeStateDelta(FrozenModel):
    api_surface_delta: SymbolDelta = Field(default_factory=SymbolDelta)
    decorators_delta: SymbolDelta = Field(default_factory=SymbolDelta)
    type_changes: tuple[JsonValue, ...] = Field(default_factory=tuple)
    effect_changes: EffectChanges = Field(default_factory=EffectChanges)
    cfg_delta: CFGDelta = Field(default_factory=CFGDelta)
    imports_delta: ImportDelta = Field(default_factory=ImportDelta)
    complexity_delta: ComplexityDelta = Field(default_factory=ComplexityDelta)
    test_surface_delta: TestSurfaceDelta = Field(default_factory=TestSurfaceDelta)
    coverage_delta: CoverageDelta | None = None
    files_touched: int = 0
    loc_delta: LocDelta = Field(default_factory=LocDelta)
    python_specific: JsonMapping | None = None
    typescript_specific: JsonMapping | None = None
