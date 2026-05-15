"""Issue body parser. Same grammar as PR body; separated for provenance attribution."""

from __future__ import annotations

from semantic_ci_code.authoring.sources.pr_body import ParsedSections, parse_pr_body


def parse_issue_body(text: str) -> ParsedSections:
    return parse_pr_body(text)
