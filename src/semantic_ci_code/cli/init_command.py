from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

from semantic_ci_code.authoring.sources import (
    CommitsParseError,
    LabelsParseError,
    parse_commit_subjects,
    parse_issue_body,
    parse_kind_labels,
    parse_pr_body,
)
from semantic_ci_code.authoring.sources.merge import (
    MergeError,
    RecipeFlagCompatibilityError,
    merge_sources,
)
from semantic_ci_code.cli.command_support import _internal_bug, _stderr, _usage_error
from semantic_ci_code.cli.exit_codes import SUCCESS
from semantic_ci_code.cli.init_recipes import RECIPES, apply_recipe
from semantic_ci_code.cli.init_recipes.feature_add_api import FeatureRecipeError

TARGET_TEMPLATE = """# semantic-ci target.yaml — declared change intent + constraints
intent: ""  # 1-line human-readable description of this PR
change:
  primary_kind: refactor  # feature | bugfix | refactor | test_update
  allowed_secondary_kinds: []
  scope:
    files: []
    modules: []
authorship:
  authors:
    - identity: ""
  declared_at: ""  # ISO-8601, e.g. 2026-05-05T12:00:00Z
# constraints: severity defaults to "hard"; "soft" or "info" weakens the gate.
constraints: []  # user constraints; templates are auto-expanded from primary_kind
"""

_SOURCE_FLAG_ATTRS = (
    "from_pr_body",
    "from_issue",
    "from_labels",
    "from_commits",
)
_EXPLICIT_INPUT_FLAG_ATTRS = (
    "add_api",
    "test_case",
    "allow_fqn",
    "allow_fqn_prefix",
    "declared_at",
)


def _is_set(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list | tuple):
        return len(value) > 0
    return True


def _flag_present(args: Namespace, attr: str) -> bool:
    return _is_set(getattr(args, attr, None))


def _serialise_recipe_payload(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _read_text_file(path_str: str, *, label: str) -> str:
    path = Path(path_str)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(f"cannot read {label} from {path_str!r}: {exc}") from exc


def _load_commit_subjects(path_str: str) -> tuple[str, ...]:
    text = _read_text_file(path_str, label="--from-commits")
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _run_recipe(args: Namespace) -> dict[str, Any]:
    recipe_id = args.recipe

    pr_body_parsed = None
    if args.from_pr_body is not None:
        pr_body_parsed = parse_pr_body(_read_text_file(args.from_pr_body, label="--from-pr-body"))

    issue_parsed = None
    if args.from_issue is not None:
        issue_parsed = parse_issue_body(_read_text_file(args.from_issue, label="--from-issue"))

    labels_consulted = args.from_labels is not None
    labels_kind = parse_kind_labels(tuple(args.from_labels)) if labels_consulted else None

    commits_consulted = args.from_commits is not None
    commits_kind = (
        parse_commit_subjects(_load_commit_subjects(args.from_commits))
        if commits_consulted
        else None
    )

    merged = merge_sources(
        recipe_id=recipe_id,
        explicit_add_api=tuple(args.add_api or ()),
        explicit_test_cases=tuple(args.test_case or ()),
        explicit_allow_fqns=tuple(args.allow_fqn or ()),
        explicit_allow_fqn_prefixes=tuple(args.allow_fqn_prefix or ()),
        declared_at=args.declared_at,
        pr_body=pr_body_parsed,
        issue=issue_parsed,
        labels_kind=labels_kind,
        commits_kind=commits_kind,
        labels_consulted=labels_consulted,
        commits_consulted=commits_consulted,
    )

    return apply_recipe(merged)


def _validate_test_case_format(values: list[str] | None) -> None:
    """Enforce canonical `path/to/test_x.py::test_y` form (§6.2.4).

    `delta/code_state_delta.py:354-355 _test_case_id` writes
    `f"{entry.test_file}::{entry.test_function}"` into
    `TestSurfaceDelta.new_cases`. Python-style FQN (`tests.test_x.test_y`)
    would compile but never match the delta, so it must be rejected at
    parse time with an explicit message.
    """
    if not values:
        return
    for value in values:
        if "::" not in value:
            raise ValueError(
                f"--test-case value {value!r} is not in canonical "
                f"'path::name' form (e.g. 'tests/test_x.py::test_y'); "
                f"recipe-generated constraints must match "
                f"TestSurfaceDelta.new_cases output of "
                f"code_state_delta._test_case_id"
            )


def _validate_recipe_relationship(args: Namespace) -> None:
    """Enforce the §6.2.3 precedence table.

    `--recipe` is the only entry point for generated targets;
    `--from-*` and explicit-input flags (`--add-api`, `--test-case`,
    `--allow-fqn`, `--allow-fqn-prefix`, `--declared-at`) require
    `--recipe` to bind to a constraint set.
    """
    if args.recipe is not None:
        if args.recipe not in RECIPES:
            valid = ", ".join(sorted(RECIPES))
            raise ValueError(f"unknown --recipe value {args.recipe!r}; valid: {valid}")
        return

    source_flag = next(
        (attr for attr in _SOURCE_FLAG_ATTRS if _flag_present(args, attr)),
        None,
    )
    if source_flag is not None:
        cli_name = "--" + source_flag.replace("_", "-")
        raise ValueError(
            f"--recipe is required when source flags ({cli_name}) are used; "
            f"recipe ID determines the constraint set"
        )

    explicit_flag = next(
        (attr for attr in _EXPLICIT_INPUT_FLAG_ATTRS if _flag_present(args, attr)),
        None,
    )
    if explicit_flag is not None:
        cli_name = "--" + explicit_flag.replace("_", "-")
        raise ValueError(
            f"--recipe is required when explicit-input flags ({cli_name}) are "
            f"used; recipe ID determines the constraint set"
        )


def run_init(args: Namespace) -> int:
    try:
        _validate_recipe_relationship(args)
        _validate_test_case_format(args.test_case)

        path = Path(args.path or ".semantic-ci/target.yaml")
        if path.exists() and not args.force:
            return _usage_error(
                FileExistsError(f"target file already exists: {path}; pass --force to overwrite")
            )
        path.parent.mkdir(parents=True, exist_ok=True)

        if args.recipe is None:
            path.write_text(TARGET_TEMPLATE, encoding="utf-8")
        else:
            payload = _run_recipe(args)
            path.write_text(_serialise_recipe_payload(payload), encoding="utf-8")

        if not args.quiet:
            _stderr(f"created {path}")
        return SUCCESS
    except (
        ValueError,
        OSError,
        MergeError,
        RecipeFlagCompatibilityError,
        FeatureRecipeError,
        LabelsParseError,
        CommitsParseError,
    ) as exc:
        return _usage_error(exc)
    except Exception as exc:
        return _internal_bug(exc, args)
