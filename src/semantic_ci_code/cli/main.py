from __future__ import annotations

import argparse
import sys

from semantic_ci_code.cli.commands.check import run_check
from semantic_ci_code.cli.commands.compare import run_compare
from semantic_ci_code.cli.commands.observe import run_observe
from semantic_ci_code.cli.commands.pre_commit import run_pre_commit
from semantic_ci_code.cli.exit_codes import SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output.json_formatter import package_version


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
    observe.add_argument("--format", choices=("json", "human"), default="json")
    observe.add_argument("--output", default=None, help="write JSON to this file instead of stdout")

    compare = subcommands.add_parser("compare", help="compare two local Python package roots")
    compare.add_argument("--baseline-dir", required=True, help="baseline directory")
    compare.add_argument("--candidate-dir", required=True, help="candidate directory")
    compare.add_argument("--target", default=None, help="Target SVP YAML file")
    compare.add_argument("--package-root-baseline", default=None, help="baseline package root")
    compare.add_argument("--package-root-candidate", default=None, help="candidate package root")
    compare.add_argument("--format", choices=("json", "human"), default=None)
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
    check.add_argument("--format", choices=("json", "human"), default=None)
    check.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )
    check.add_argument("--strict-repair", action="store_true")
    check.add_argument("--no-fetch", action="store_true")
    check.add_argument("--allow-dirty", action="store_true")
    check.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="disable ANSI color in human output",
    )

    pre_commit = subcommands.add_parser(
        "pre-commit",
        help="compare staged index against HEAD",
    )
    pre_commit.add_argument("--target", default=None, help="Target SVP YAML file")
    pre_commit.add_argument(
        "--package-root",
        default=".",
        help="repo-relative Python package root inside HEAD and the staged index",
    )
    pre_commit.add_argument("--format", choices=("json", "human"), default=None)
    pre_commit.add_argument(
        "--output",
        default=None,
        help="write output to this file instead of stdout",
    )
    pre_commit.add_argument("--strict-repair", action="store_true")
    pre_commit.add_argument(
        "--no-color",
        action="store_true",
        default=argparse.SUPPRESS,
        help="disable ANSI color in human output",
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
    if args.subcommand == "pre-commit":
        return run_pre_commit(args)

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
