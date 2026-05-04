from __future__ import annotations

import argparse
import sys

from semantic_ci_code.cli.commands.observe import run_observe
from semantic_ci_code.cli.exit_codes import SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output.json_basic import package_version


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(package_version())
        return SUCCESS

    if args.subcommand == "observe":
        return run_observe(args)

    parser.print_help(sys.stderr)
    return USAGE_ERROR


if __name__ == "__main__":
    sys.exit(main())
