"""Parse intent-declaring sections out of an issue body markdown blob.

Semantically identical to `pr_body.py` (same registry, same grammar);
the entry point is duplicated so `merge.py` can keep `pr_body` (strong)
and `issue` (medium) source layers separate when assembling
`generation_metadata.source_surfaces`.
"""

from __future__ import annotations

from semantic_ci_code.authoring.sources.pr_body import (
    ParsedSections,
)
from semantic_ci_code.authoring.sources.pr_body import (
    parse_pr_body as _parse_markdown_sections,
)


def parse_issue_body(text: str) -> ParsedSections:
    """Issue body parser. Same grammar as PR body; separated for provenance."""
    return _parse_markdown_sections(text)
