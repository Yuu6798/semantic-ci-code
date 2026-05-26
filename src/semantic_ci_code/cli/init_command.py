from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

from semantic_ci_code.authoring.canonical import (
    is_canonical_fqn,
    is_canonical_fqn_prefix,
    is_canonical_test_id,
)
from semantic_ci_code.authoring.sources import (
    CommitsParseError,
    LabelsParseError,
    parse_commit_subjects,
    parse_issue_body,
    parse_kind_labels,
    parse_pr_body,
)
from semantic_ci_code.authoring.sources.merge import (
    RECIPE_BUGFIX_REGRESSION_TEST,
    RECIPE_FEATURE_ADD_API,
    RECIPE_REFACTOR_PRESERVE_API,
    RECIPE_TEST_UPDATE_ADD_TEST_CASE,
    MergeError,
    RecipeFlagCompatibilityError,
    merge_sources,
)
from semantic_ci_code.cli.command_support import _internal_bug, _stderr, _usage_error
from semantic_ci_code.cli.doctor_support import PackageRootError, resolve_package_root
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

_SOURCE_FLAG_ATTRS = ("from_pr_body", "from_issue", "from_labels", "from_commits")
_EXPLICIT_INPUT_FLAG_ATTRS = (
    "add_api",
    "test_case",
    "allow_fqn",
    "allow_fqn_prefix",
    "declared_at",
)
_RECIPE_NOTES: dict[str, str] = {
    RECIPE_FEATURE_ADD_API: (
        "note: template locks effect_changes.added = () and "
        "api_surface_delta.removed_public = (); new effects require "
        "effects.allow_new in target.yaml"
    ),
    RECIPE_BUGFIX_REGRESSION_TEST: (
        "note: template locks api_surface_public to baseline; API changes require "
        "a different recipe"
    ),
    RECIPE_REFACTOR_PRESERVE_API: (
        "note: template locks api_surface, type_relations, effect_changes, "
        "and test_surface to baseline"
    ),
    RECIPE_TEST_UPDATE_ADD_TEST_CASE: (
        "note: template locks api_surface, effect_changes, and imports to baseline"
    ),
}


def _flag_present(args: Namespace, attr: str) -> bool:
    value = getattr(args, attr, None)
    if value is None:
        return False
    if isinstance(value, list | tuple):
        return len(value) > 0
    return True


def _read_text_file(path_str: str, *, label: str) -> str:
    try:
        return Path(path_str).read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(f"cannot read {label} from {path_str!r}: {exc}") from exc


def _validate_recipe_relationship(args: Namespace) -> None:
    if args.recipe is not None:
        if args.recipe not in RECIPES:
            valid = ", ".join(sorted(RECIPES))
            raise ValueError(f"unknown --recipe value {args.recipe!r}; valid: {valid}")
        return

    for attr in (*_SOURCE_FLAG_ATTRS, *_EXPLICIT_INPUT_FLAG_ATTRS):
        if _flag_present(args, attr):
            cli_name = "--" + attr.replace("_", "-")
            kind = "source" if attr in _SOURCE_FLAG_ATTRS else "explicit-input"
            raise ValueError(
                f"--recipe is required when {kind} flags ({cli_name}) are used; "
                f"recipe ID determines the constraint set"
            )


def _validate_test_case_format(values: list[str] | None) -> None:
    for value in values or ():
        if not is_canonical_test_id(value):
            raise ValueError(
                f"--test-case value {value!r} is not in canonical 'path::name' form "
                f"(e.g. 'tests/test_x.py::test_y' or 'tests/test_x.py::TestClass::test_method'); "
                f"recipe-generated constraints must match TestSurfaceDelta.new_cases output of "
                f"code_state_delta._test_case_id (path and identifier segments only, no "
                f"parametrize brackets or stray spaces)"
            )


def _validate_fqn_values(values: list[str] | None, *, flag: str) -> None:
    for value in values or ():
        if not is_canonical_fqn(value):
            raise ValueError(
                f"{flag} value {value!r} is not a valid dotted FQN (e.g. "
                f"'pkg.module.symbol'); each segment must be a Python identifier and "
                f"the value must contain at least one '.', not contain '::', and not "
                f"start or end with '.'"
            )


def _validate_fqn_prefix_values(values: list[str] | None) -> None:
    for value in values or ():
        if not is_canonical_fqn_prefix(value):
            raise ValueError(
                f"--allow-fqn-prefix value {value!r} is not a valid FQN prefix; the "
                f"value must end with exactly one '.' (e.g. 'pkg.legacy.') so the "
                f"allowlist matches the intended package subtree only — bare 'legacy' "
                f"would also permit 'legacy2.Foo' through the evaluator's startswith() "
                f"check, and doubled dots like 'pkg..' would never match real FQNs"
            )


def _validate_intent(value: str | None) -> None:
    if value is not None and ("\n" in value or "\r" in value):
        raise ValueError(
            "--intent must be a single line; newline and carriage return characters are not allowed"
        )


def _validate_doctor_flags(args: Namespace) -> None:
    if args.package_root is not None and not args.doctor:
        raise ValueError("--package-root is only valid with --doctor")


def _run_recipe(args: Namespace) -> dict[str, Any]:
    pr_body_parsed = None
    if args.from_pr_body is not None:
        pr_body_parsed = parse_pr_body(_read_text_file(args.from_pr_body, label="--from-pr-body"))

    issue_parsed = None
    if args.from_issue is not None:
        issue_parsed = parse_issue_body(_read_text_file(args.from_issue, label="--from-issue"))

    labels_consulted = args.from_labels is not None
    labels_kind = parse_kind_labels(tuple(args.from_labels)) if labels_consulted else None

    commits_consulted = args.from_commits is not None
    if commits_consulted:
        text = _read_text_file(args.from_commits, label="--from-commits")
        subjects = tuple(line.strip() for line in text.splitlines() if line.strip())
        commits_kind = parse_commit_subjects(subjects)
    else:
        commits_kind = None

    merged = merge_sources(
        recipe_id=args.recipe,
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
        intent=args.intent or "",
    )
    return apply_recipe(merged)


def _bare_scaffold_with_intent(intent: str) -> dict[str, Any]:
    return {
        "intent": intent,
        "change": {
            "primary_kind": "refactor",
            "allowed_secondary_kinds": [],
            "scope": {"files": [], "modules": []},
        },
        "authorship": {
            "authors": [{"identity": ""}],
            "declared_at": "",
        },
        "constraints": [],
    }


def _has_test_surface_constraint(payload: dict[str, Any]) -> bool:
    for constraint in payload.get("constraints", ()):
        if constraint.get("target", "").startswith("test_surface_delta"):
            return True
    return False


def _stderr_block(text: str) -> None:
    for line in text.rstrip("\n").splitlines():
        _stderr(line)


def _run_inline_doctor(path: Path, args: Namespace) -> None:
    from semantic_ci_code.authoring import detect_advisories
    from semantic_ci_code.cli.output.doctor_human import format_doctor_human
    from semantic_ci_code.compiler.target_compiler import compile_target_svp

    yaml_text = path.read_text(encoding="utf-8")
    compiled = compile_target_svp(yaml_text)
    package_root = resolve_package_root(args.package_root)
    advisories = detect_advisories(
        compiled,
        package_root=package_root,
        files_touched=None,
    )
    if args.quiet:
        return
    if advisories:
        _stderr_block(format_doctor_human(advisories))
    else:
        _stderr("target-doctor: no advisories")


def _print_next_commands(path: Path, *, include_validate_plan: bool) -> None:
    _stderr("next:")
    _stderr(f"  semantic-ci compile --target {path} --format human")
    _stderr(f"  semantic-ci target-doctor --target {path} --package-root .")
    if include_validate_plan:
        _stderr(f"  semantic-ci validate-plan --target {path} --adapter codex")


def run_init(args: Namespace) -> int:
    try:
        _validate_doctor_flags(args)
        _validate_intent(args.intent)
        _validate_recipe_relationship(args)
        _validate_test_case_format(args.test_case)
        _validate_fqn_values(args.add_api, flag="--add-api")
        _validate_fqn_values(args.allow_fqn, flag="--allow-fqn")
        _validate_fqn_prefix_values(args.allow_fqn_prefix)

        path = Path(args.path or ".semantic-ci/target.yaml")
        if path.exists() and not args.force:
            return _usage_error(
                FileExistsError(f"target file already exists: {path}; pass --force to overwrite")
            )
        path.parent.mkdir(parents=True, exist_ok=True)

        if args.recipe is None:
            payload = None
            if args.intent:
                scaffold = _bare_scaffold_with_intent(args.intent)
                path.write_text(
                    yaml.safe_dump(scaffold, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
            else:
                path.write_text(TARGET_TEMPLATE, encoding="utf-8")
        else:
            payload = _run_recipe(args)
            path.write_text(
                yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

        if not args.quiet:
            _stderr(f"created {path}")
            if args.recipe is not None:
                note = _RECIPE_NOTES.get(args.recipe)
                if note:
                    _stderr(note)
                if payload is not None and _has_test_surface_constraint(payload):
                    _stderr(
                        "note: this target expects test files; ensure --package-root "
                        "covers your test directory"
                    )
        if args.doctor:
            _run_inline_doctor(path, args)
        if not args.quiet:
            _print_next_commands(path, include_validate_plan=args.recipe is not None)
        return SUCCESS
    except (
        ValueError,
        PackageRootError,
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
