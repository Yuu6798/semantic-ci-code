"""Validate PR-body dogfooding disclosure.

This is intentionally small and dependency-free so GitHub Actions can run it
before installing the project. It does not try to prove the commands were
executed; it makes the discipline explicit and reviewable:

* dogfooding is the default expected path (`Status: performed`)
* if dogfooding is skipped, the PR body must say why (`Reason: ...`)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STATUS_RE = re.compile(r"^\s*(?:[-*]\s*)?Status:\s*(performed|skipped)\s*$", re.I)
LABEL_RE = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z ]+):\s*(.*)$")
DOGFOOD_HEADING = "## Dogfooding"


class DogfoodDisclosureError(ValueError):
    pass


def _extract_section(markdown: str, heading: str) -> str | None:
    lines = markdown.splitlines()
    section: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == heading:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            section.append(line)
    text = "\n".join(section).strip()
    return text if text else None


def _meaningful(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    return not (stripped.startswith("<") and stripped.endswith(">"))


def _label_has_content(section: str, labels: frozenset[str]) -> bool:
    lines = section.splitlines()
    for index, line in enumerate(lines):
        match = LABEL_RE.match(line)
        if match is None:
            continue
        label = match.group(1).strip().lower()
        if label not in labels:
            continue
        if _meaningful(match.group(2)):
            return True
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if not stripped:
                continue
            following_match = LABEL_RE.match(following)
            if following_match is not None:
                break
            if _meaningful(stripped.lstrip("-* ")):
                return True
    return False


def validate_pr_body(body: str) -> None:
    section = _extract_section(body, DOGFOOD_HEADING)
    if section is None:
        raise DogfoodDisclosureError(
            "PR body must include `## Dogfooding` with `Status: performed` or `Status: skipped`."
        )

    status_match = next(
        (STATUS_RE.match(line) for line in section.splitlines() if STATUS_RE.match(line)),
        None,
    )
    if status_match is None:
        raise DogfoodDisclosureError(
            "`## Dogfooding` must include `Status: performed` or `Status: skipped`."
        )

    status = status_match.group(1).lower()
    if status == "skipped":
        if not _label_has_content(section, frozenset({"reason", "skip reason"})):
            raise DogfoodDisclosureError(
                "`Status: skipped` must include a non-empty `Reason:` line."
            )
        return

    if not _label_has_content(section, frozenset({"commands", "command", "result", "evidence"})):
        raise DogfoodDisclosureError(
            "`Status: performed` must include non-empty dogfood evidence "
            "(`Commands:`, `Result:`, or `Evidence:`)."
        )


def _body_from_event(path: Path) -> str | None:
    event = json.loads(path.read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    body = pull_request.get("body") or ""
    return str(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--event-path", type=Path)
    source.add_argument("--body-file", type=Path)
    args = parser.parse_args(argv)

    if args.event_path is not None:
        body = _body_from_event(args.event_path)
        if body is None:
            return 0
    else:
        body = args.body_file.read_text(encoding="utf-8")

    try:
        validate_pr_body(body)
    except DogfoodDisclosureError as exc:
        print(f"dogfooding disclosure check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
