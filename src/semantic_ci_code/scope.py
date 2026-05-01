from __future__ import annotations

from pydantic import BaseModel, Field

SCOPE_STATEMENT = "This is not a linter. This is not a type checker. This is not a test runner."


class ProjectScope(BaseModel):
    """Repository boundary for the bootstrap package."""

    product_name: str = "Semantic CI Code Edition"
    scope_statement: str = SCOPE_STATEMENT
    compares: tuple[str, ...] = Field(
        default=(
            "declared change intent",
            "expected code state",
            "baseline code state",
            "observed code state",
        ),
        min_length=1,
    )
    emits: tuple[str, ...] = Field(default=("semantic diff", "repair instructions"), min_length=1)
    deterministic: bool = True
    requires_llm: bool = False
    requires_api_key: bool = False


def default_scope() -> ProjectScope:
    return ProjectScope()
