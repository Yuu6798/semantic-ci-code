"""Source parsers for `semantic-ci init --recipe --from-*` (Brief 8 / CSCI-42).

Each module here owns one input surface (`pr_body`, `issue`, `labels`,
`commits`) and exposes a pure parsing function. `merge.py` then layers
the parsed contributions per `docs/brief_8_planning.md §6.2.3` strength
and conflict rules (C1〜C4).
"""

from semantic_ci_code.authoring.sources.commits import (
    CommitsParseError,
    parse_commit_subjects,
)
from semantic_ci_code.authoring.sources.issue import parse_issue_body
from semantic_ci_code.authoring.sources.labels import (
    LabelsParseError,
    parse_kind_labels,
)
from semantic_ci_code.authoring.sources.pr_body import (
    ParsedSections,
    SectionParseError,
    parse_pr_body,
)

__all__ = [
    "CommitsParseError",
    "LabelsParseError",
    "ParsedSections",
    "SectionParseError",
    "parse_commit_subjects",
    "parse_issue_body",
    "parse_kind_labels",
    "parse_pr_body",
]
