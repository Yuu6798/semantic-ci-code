from __future__ import annotations

import argparse
import sys

from semantic_ci_code.cli.commands.check import run_check
from semantic_ci_code.cli.commands.compare import run_compare
from semantic_ci_code.cli.commands.compile import run_compile
from semantic_ci_code.cli.commands.compile_repair import run_compile_repair
from semantic_ci_code.cli.commands.observe import run_observe
from semantic_ci_code.cli.commands.ssp import run_ssp
from semantic_ci_code.cli.commands.target_catalog import run_target_catalog
from semantic_ci_code.cli.commands.target_doctor import run_target_doctor
from semantic_ci_code.cli.commands.validate_plan import run_validate_plan
from semantic_ci_code.cli.exit_codes import SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.init_command import run_init
from semantic_ci_code.cli.output.json_formatter import package_version

_ALL_FORMATS = ("json", "human", "sarif", "gh-actions")
_VERDICT_FORMATS = _ALL_FORMATS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="semantic-ci")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument(
        "--language",
        choices=("python",),
        default="python",
        help="source language to analyze; CSCI-15 supports python only",
    )
    parser.add_argument("--no-color", action="store_true", help="reserved for human output")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("--quiet", action="store_true", help="suppress progress diagnostics")
    verbosity.add_argument("--verbose", action="store_true", help="print progress diagnostics")

    subcommands = parser.add_subparsers(dest="subcommand")
    observe = subcommands.add_parser("observe", help="dump a Python CodeState as JSON")
    observe.add_argument("--package-root", default=".", help="Python package root to observe")
    observe.add_argument(
        "--paths",
        nargs="+",
        default=None,
        help="optional Python files or directories to limit per-file extractors",
    )
    observe.add_argument("--format", choices=_ALL_FORMATS, default="json")
    observe.add_argument("--output", default=None, help="write JSON to this file instead of stdout")

    compare = subcommands.add_parser("compare", help="compare two local Python package roots")
    compare.add_argument("--baseline-dir", required=True, help="baseline directory")
    compare.add_argument("--candidate-dir", required=True, help="candidate directory")
    compare.add_argument("--target", default=None, help="Target SVP YAML file")
    compare.add_argument("--package-root-baseline", default=None, help="baseline package root")
    compare.add_argument("--package-root-candidate", default=None, help="candidate package root")
    compare.add_argument("--format", choices=_VERDICT_FORMATS, default=None)
    compare.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )
    compare.add_argument("--strict-repair", action="store_true")
    compare.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="disable ANSI color in human output",
    )

    check = subcommands.add_parser("check", help="compare git refs using temporary worktrees")
    check.add_argument("--baseline-rev", default=None, help="baseline git ref")
    check.add_argument("--candidate-rev", default=None, help="candidate git ref")
    check.add_argument("--target", default=None, help="Target SVP YAML file")
    check.add_argument(
        "--package-root",
        default=".",
        help="repo-relative Python package root inside each git tree",
    )
    check.add_argument("--format", choices=_VERDICT_FORMATS, default=None)
    check.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )
    check.add_argument("--strict-repair", action="store_true")
    check.add_argument(
        "--mode",
        choices=("smoke", "full"),
        default=None,
        help="execution mode; defaults to SEMANTIC_CI_MODE or full",
    )
    check.add_argument("--no-fetch", action="store_true")
    check.add_argument(
        "--extractor-timeout",
        type=float,
        default=None,
        help="per-dimension extractor timeout in seconds; omitted means no timeout",
    )
    check.add_argument(
        "--sensor-baseline",
        default=None,
        help="prebuilt baseline SensorState JSON for suite security verdict integration",
    )
    check.add_argument(
        "--sensor-candidate",
        default=None,
        help="prebuilt candidate SensorState JSON for suite security verdict integration",
    )
    check.add_argument(
        "--as-of",
        default=None,
        help="YYYY-MM-DD date used for security suppression expiry; defaults to today",
    )
    check.add_argument(
        "--advisory-sensor",
        action="append",
        default=None,
        metavar="ADAPTER=PATH",
        help=(
            "recorded advisory sensor payload; repeatable; "
            "currently supports codex-security=<json-path>"
        ),
    )
    check.add_argument(
        "--advisory-mutes",
        default=None,
        help="YAML advisory mute ledger; valid only with --advisory-sensor",
    )
    check.add_argument(
        "--baseline-source",
        choices=("commit", "working-tree", "staged-index"),
        default="commit",
        help="baseline snapshot source: commit ref, working tree, or staged index",
    )
    check.add_argument(
        "--candidate-source",
        choices=("commit", "working-tree", "staged-index"),
        default="commit",
        help="candidate snapshot source: commit ref, working tree, or staged index",
    )
    check.add_argument("--no-cache", action="store_true", help="disable CodeState cache")
    check.add_argument(
        "--cache-dir",
        default=None,
        help="cache root directory; defaults to <repo>/.semantic-ci/cache",
    )
    check.add_argument(
        "--cache-max-bytes",
        default=None,
        help="maximum cache size in bytes; 0 disables eviction",
    )
    check.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="disable ANSI color in human output",
    )

    compile_cmd = subcommands.add_parser("compile", help="compile target.yaml without judging")
    compile_cmd.add_argument("--target", default=None, help="Target SVP YAML file")
    compile_cmd.add_argument("target_path", nargs="?", help="Target SVP YAML file")
    compile_cmd.add_argument("--format", choices=_ALL_FORMATS, default=None)
    compile_cmd.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )
    compile_cmd.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="disable ANSI color in human output",
    )

    compile_repair = subcommands.add_parser(
        "compile-repair",
        help="render a RepairPlan for a coding adapter",
    )
    compile_repair.add_argument("--input", default=None, help="input JSON file; stdin by default")
    compile_repair.add_argument(
        "--adapter",
        choices=("claude-code", "cursor", "codex"),
        required=True,
        help="repair compiler adapter to render with",
    )
    compile_repair.add_argument(
        "--output",
        default=None,
        help="write rendered output to this file instead of stdout",
    )
    compile_repair.add_argument("--format", choices=("text", "json"), default="text")
    compile_repair.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="accepted for CLI consistency; compile-repair output is not colorized",
    )

    validate_plan = subcommands.add_parser(
        "validate-plan",
        help="render pre-generation plan guidance for a coding adapter",
    )
    validate_plan.add_argument("--target", required=True, help="Target SVP YAML file")
    validate_plan.add_argument(
        "--adapter",
        choices=("claude-code", "cursor", "codex"),
        required=True,
        help="repair compiler adapter to render with",
    )
    validate_plan.add_argument("--baseline-rev", default=None, help="baseline git ref")
    validate_plan.add_argument("--baseline-dir", default=None, help="baseline directory")
    validate_plan.add_argument(
        "--package-root",
        default=".",
        help="repo-relative package root inside the baseline tree",
    )
    validate_plan.add_argument("--format", choices=("text", "json"), default="text")
    validate_plan.add_argument(
        "--output",
        default=None,
        help="write rendered output to this file instead of stdout",
    )
    validate_plan.add_argument("--no-fetch", action="store_true")
    validate_plan.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="accepted for CLI consistency; validate-plan output is not colorized",
    )

    init = subcommands.add_parser("init", help="scaffold a semantic-ci target.yaml")
    init.add_argument("--path", default=None, help="target.yaml path to create")
    init.add_argument("--force", action="store_true", help="overwrite an existing file")
    init.add_argument(
        "--intent",
        default=None,
        metavar="TEXT",
        help="1-line human-readable intent (populates the intent field)",
    )
    init.add_argument(
        "--recipe",
        default=None,
        choices=(
            "feature:add-api",
            "bugfix:regression-test",
            "refactor:preserve-api-with-allowlist",
            "test-update:add-test-case",
            "security:deny-dangerous-imports",
            "security:deny-dangerous-effects",
            "security:preserve-auth-guards",
        ),
        help="generate target.yaml from a recipe instead of the bare scaffold",
    )
    init.add_argument(
        "--add-api",
        action="append",
        default=None,
        metavar="FQN",
        help="explicit public API FQN to declare (feature:add-api only); repeatable",
    )
    init.add_argument(
        "--test-case",
        action="append",
        default=None,
        metavar="PATH::NAME",
        help=("canonical test case ID (path/to/test_file.py::test_function); repeatable"),
    )
    init.add_argument(
        "--allow-fqn",
        action="append",
        default=None,
        metavar="FQN",
        help=("FQN to allow in api_surface.allow_changes (refactor recipe only); repeatable"),
    )
    init.add_argument(
        "--allow-fqn-prefix",
        action="append",
        default=None,
        metavar="PREFIX",
        help=(
            "FQN prefix to allow in api_surface.allow_changes (refactor recipe only); repeatable"
        ),
    )
    init.add_argument(
        "--declared-at",
        default=None,
        help="explicit ISO-8601 timestamp for authorship.declared_at",
    )
    init.add_argument(
        "--from-pr-body",
        default=None,
        metavar="PATH",
        help="path to a markdown file containing the PR body",
    )
    init.add_argument(
        "--from-issue",
        default=None,
        metavar="PATH",
        help="path to a markdown file containing an issue body",
    )
    init.add_argument(
        "--from-labels",
        nargs="+",
        default=None,
        metavar="LABEL",
        help="GitHub labels for primary_kind validation; e.g. kind:feature",
    )
    init.add_argument(
        "--from-commits",
        default=None,
        metavar="PATH",
        help=(
            "path to a text file containing one commit subject line per row; "
            "Conventional Commits prefix feeds the primary_kind hint"
        ),
    )
    init.add_argument(
        "--doctor",
        action="store_true",
        default=False,
        help="run target-doctor inline after generating the target",
    )
    init.add_argument(
        "--package-root",
        default=None,
        help="Python package root for --doctor advisory D1 detection",
    )

    target_doctor = subcommands.add_parser(
        "target-doctor",
        help="render target.yaml authoring advisories (verdict 不参加)",
    )
    target_doctor.add_argument("--target", default=None, help="Target SVP YAML file")
    target_doctor.add_argument(
        "--package-root",
        default=".",
        help="package root used to detect ADVISORY-D1 (test_surface visibility)",
    )
    target_doctor.add_argument(
        "--baseline-rev",
        default=None,
        help="baseline git ref for ADVISORY-D4 / D6 (diff-aware hazards)",
    )
    target_doctor.add_argument(
        "--candidate-rev",
        default=None,
        help="candidate git ref for ADVISORY-D4 / D6; defaults to HEAD",
    )
    target_doctor.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="output format; advisor envelope schema_version='advisory-1' (json)",
    )
    target_doctor.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )

    target_catalog = subcommands.add_parser(
        "target-catalog",
        help="render target/operator/template catalog for target.yaml authoring",
    )
    target_catalog.add_argument(
        "--format",
        choices=("json", "human"),
        default="json",
        help="output format; catalog envelope schema_version='catalog-1' (json)",
    )
    target_catalog.add_argument(
        "--kind",
        choices=("feature", "bugfix", "refactor", "test_update", "generic"),
        default=None,
        help="narrow the templates section to one primary change kind",
    )
    target_catalog.add_argument(
        "--target-path",
        default=None,
        help="narrow the targets section to one target path",
    )
    target_catalog.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )

    ssp = subcommands.add_parser(
        "ssp",
        help="run Semantic Security Protocol sensors and render SSP envelopes",
    )
    ssp_subcommands = ssp.add_subparsers(dest="ssp_subcommand")
    ssp_subcommands.required = True

    ssp_scan = ssp_subcommands.add_parser("scan", help="run an SSP sensor on two trees")
    ssp_scan.add_argument(
        "--sensor",
        choices=("semgrep", "pip-audit"),
        required=True,
        help="SSP sensor adapter to run",
    )
    ssp_scan.add_argument("--config", default=None, help="Semgrep ruleset path")
    ssp_scan.add_argument("--baseline-dir", required=True, help="baseline project directory")
    ssp_scan.add_argument("--candidate-dir", required=True, help="candidate project directory")
    ssp_scan.add_argument(
        "--package-root",
        default=".",
        help="package root inside each tree for Semgrep scans",
    )
    ssp_scan.add_argument(
        "--format",
        choices=("json", "human", "sarif"),
        default="json",
        help="SSP output format",
    )
    ssp_scan.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )

    ssp_from_json = ssp_subcommands.add_parser(
        "from-json",
        help="compute an SSP envelope from two SensorOutput JSON files",
    )
    ssp_from_json.add_argument("--baseline", required=True, help="baseline SensorOutput JSON")
    ssp_from_json.add_argument("--candidate", required=True, help="candidate SensorOutput JSON")
    ssp_from_json.add_argument(
        "--format",
        choices=("json", "human", "sarif"),
        default="json",
        help="SSP output format",
    )
    ssp_from_json.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(package_version())
        return SUCCESS

    if args.subcommand == "observe":
        return run_observe(args)
    if args.subcommand == "compare":
        return run_compare(args)
    if args.subcommand == "check":
        return run_check(args)
    if args.subcommand == "compile":
        return run_compile(args)
    if args.subcommand == "compile-repair":
        return run_compile_repair(args)
    if args.subcommand == "validate-plan":
        return run_validate_plan(args)
    if args.subcommand == "init":
        return run_init(args)
    if args.subcommand == "target-doctor":
        return run_target_doctor(args)
    if args.subcommand == "target-catalog":
        return run_target_catalog(args)
    if args.subcommand == "ssp":
        return run_ssp(args)

    parser.print_help(sys.stderr)
    return USAGE_ERROR


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue


if __name__ == "__main__":
    sys.exit(main())
