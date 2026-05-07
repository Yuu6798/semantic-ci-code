from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALUATOR_DIR = REPO_ROOT / "src" / "semantic_ci_code" / "evaluator"
FORBIDDEN_COMPILER_NAMES = {"CompiledAuthor", "CompiledAuthorship"}
FORBIDDEN_AUTHORSHIP_NAMES = {"Author", "Authorship"}
TARGET_SVP_MODULE = "semantic_ci_code.framework.target_svp"


def test_evaluator_does_not_import_authorship_symbols():
    for path in sorted(EVALUATOR_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                _assert_import_node_has_no_authorship_module(path, node)
            elif isinstance(node, ast.ImportFrom):
                _assert_import_from_has_no_authorship_symbols(path, node)


def _assert_import_node_has_no_authorship_module(path: Path, node: ast.Import) -> None:
    for alias in node.names:
        assert alias.name != TARGET_SVP_MODULE, f"{path}: forbidden import {alias.name}"


def _assert_import_from_has_no_authorship_symbols(path: Path, node: ast.ImportFrom) -> None:
    module = node.module or ""
    for alias in node.names:
        assert alias.name not in FORBIDDEN_COMPILER_NAMES, f"{path}: forbidden import {alias.name}"
        if module == TARGET_SVP_MODULE:
            assert alias.name not in FORBIDDEN_AUTHORSHIP_NAMES, (
                f"{path}: forbidden import {alias.name} from {module}"
            )
