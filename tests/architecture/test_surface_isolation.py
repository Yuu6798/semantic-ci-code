"""Brief 8 / CSCI-43/44 architecture invariants.

INV-2 (`docs/brief_8_planning.md §5.2`): `cli.commands.check` and the
other verdict-bearing handlers must not transitively import the new
Authoring or target-audit modules (`init --recipe`, `target-doctor`,
`target-catalog`, `authoring/`). `cli.main` subparser registration is
excluded — it is a dispatcher concern, not a verdict-semantic one.
The Advisor surface (`compile-repair`, `validate-plan`,
`repair_compiler/adapters/*`) is explicitly exempt from INV-2 (see
`docs/target_authoring_surface.md` Section E).

INV-4: target-doctor, target-catalog, and the authoring layer must not transitively
import `httpx`, `requests`, `openai`, `anthropic`, `urllib3`, `socket`, or `ssl`. The
brief is fully deterministic; LLM / network paths land in Brief 8b, not
in Brief 8.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

PROJECT_PREFIX = "semantic_ci_code"
PROJECT_ROOT = Path(__file__).resolve().parents[2] / "src"

VERDICT_PATH_HANDLERS = (
    "semantic_ci_code.cli.commands.check",
    "semantic_ci_code.cli.commands.compare",
)

AUTHORING_FORBIDDEN_FOR_VERDICT_PATH = (
    "semantic_ci_code.authoring",
    "semantic_ci_code.authoring.advisory",
    "semantic_ci_code.authoring.catalog",
    "semantic_ci_code.authoring.hazards",
    "semantic_ci_code.cli.commands.target_catalog",
    "semantic_ci_code.cli.commands.target_doctor",
    "semantic_ci_code.cli.output.catalog_human",
    "semantic_ci_code.cli.output.catalog_json",
    "semantic_ci_code.cli.output.doctor_human",
    "semantic_ci_code.cli.output.doctor_json",
)

NETWORK_LLM_FORBIDDEN = (
    "httpx",
    "requests",
    "openai",
    "anthropic",
    "urllib3",
    "socket",
    "ssl",
)

CSCI_44_MODULES = (
    "semantic_ci_code.authoring.catalog",
    "semantic_ci_code.cli.commands.target_catalog",
    "semantic_ci_code.cli.output.catalog_human",
    "semantic_ci_code.cli.output.catalog_json",
)


def _module_to_path(module_name: str) -> Path | None:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, AttributeError, ValueError):
        return None
    if spec is None or spec.origin is None or spec.origin == "built-in":
        return None
    path = Path(spec.origin)
    if not path.exists():
        return None
    return path


def _direct_imports(path: Path) -> set[str]:
    """Return module names directly imported by this file.

    For `from X import Y`, the module name `X` is always added, and
    `X.Y` is also added when `X.Y` resolves to an importable module
    (i.e., `Y` is a submodule, not just a symbol). This matters because
    `from semantic_ci_code.cli.output import doctor_human` makes
    `doctor_human` a real module dependency, while `from foo import
    Symbol` does not.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            base = node.module
            imports.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}"
                if _module_to_path(candidate) is not None:
                    imports.add(candidate)
    return imports


def _transitive_closure(root_module: str) -> set[str]:
    """Static AST closure: collects every module name reachable via
    static `import` / `from ... import` statements. Recurses only into
    project-internal modules (PROJECT_PREFIX) so external deps appear
    in the closure as their advertised name without descending into
    site-packages.
    """
    visited: set[str] = set()
    queue: list[str] = [root_module]
    while queue:
        module_name = queue.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        if not module_name.startswith(PROJECT_PREFIX):
            continue
        path = _module_to_path(module_name)
        if path is None:
            continue
        for imported in _direct_imports(path):
            if imported not in visited:
                queue.append(imported)
    return visited


def _is_forbidden_match(module: str, forbidden: tuple[str, ...]) -> str | None:
    for banned in forbidden:
        if module == banned or module.startswith(banned + "."):
            return banned
    return None


# ---------------------------------------------------------------------------
# INV-2 — verdict-path handlers do not import authoring / target-doctor
# ---------------------------------------------------------------------------


def test_inv2_check_handler_does_not_import_authoring_modules():
    closure = _transitive_closure("semantic_ci_code.cli.commands.check")
    leaks = sorted(
        m for m in closure if _is_forbidden_match(m, AUTHORING_FORBIDDEN_FOR_VERDICT_PATH)
    )
    assert not leaks, (
        f"cli.commands.check transitively imports authoring/target-doctor "
        f"modules (INV-2 violation): {leaks}"
    )


def test_inv2_compare_handler_does_not_import_authoring_modules():
    closure = _transitive_closure("semantic_ci_code.cli.commands.compare")
    leaks = sorted(
        m for m in closure if _is_forbidden_match(m, AUTHORING_FORBIDDEN_FOR_VERDICT_PATH)
    )
    assert not leaks, f"cli.commands.compare INV-2 violation: {leaks}"


def test_inv2_main_dispatcher_is_excluded_from_isolation():
    """`cli.main` is a dispatcher, not a verdict-semantic module.

    The closure of `cli.main` *will* include target-doctor (subparser
    registration), but that does not violate INV-2. This test pins that
    the exemption is intentional: if someone refactors the dispatcher
    such that `cli.main` becomes verdict-semantic, this assertion stops
    being valid and the test should be re-evaluated.
    """
    closure = _transitive_closure("semantic_ci_code.cli.main")
    assert "semantic_ci_code.cli.commands.target_doctor" in closure
    assert "semantic_ci_code.cli.commands.target_catalog" in closure


# ---------------------------------------------------------------------------
# INV-4 — no-LLM / no-network for the authoring / advisor surface
# ---------------------------------------------------------------------------


def test_inv4_target_doctor_does_not_import_network_or_llm():
    closure = _transitive_closure("semantic_ci_code.cli.commands.target_doctor")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
    assert not leaks, (
        f"target-doctor transitively imports network / LLM client (INV-4 violation): {leaks}"
    )


def test_inv4_authoring_package_does_not_import_network_or_llm():
    closure = _transitive_closure("semantic_ci_code.authoring")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
    assert not leaks, f"authoring/ INV-4 violation: {leaks}"


def test_inv4_authoring_hazards_does_not_import_network_or_llm():
    closure = _transitive_closure("semantic_ci_code.authoring.hazards")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
    assert not leaks, f"authoring.hazards INV-4 violation: {leaks}"


def test_inv4_csci44_modules_do_not_import_network_or_llm():
    failures: dict[str, list[str]] = {}
    for module in CSCI_44_MODULES:
        closure = _transitive_closure(module)
        leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
        if leaks:
            failures[module] = leaks
    assert not failures, f"CSCI-44 INV-4 violation: {failures}"


# ---------------------------------------------------------------------------
# INV-4 (CSCI-42 additions) — init recipes and PR-metadata sources are
# deterministic and must not transitively pull in network / LLM clients.
# ---------------------------------------------------------------------------


CSCI_42_MODULES = (
    "semantic_ci_code.cli.init_command",
    "semantic_ci_code.cli.init_recipes",
    "semantic_ci_code.cli.init_recipes.feature_add_api",
    "semantic_ci_code.cli.init_recipes.bugfix_regression_test",
    "semantic_ci_code.cli.init_recipes.refactor_preserve_api",
    "semantic_ci_code.cli.init_recipes.test_update_add_test_case",
    "semantic_ci_code.cli.init_recipes.security_deny_dangerous_imports",
    "semantic_ci_code.cli.init_recipes.security_deny_dangerous_effects",
    "semantic_ci_code.authoring.sources",
    "semantic_ci_code.authoring.sources.pr_body",
    "semantic_ci_code.authoring.sources.issue",
    "semantic_ci_code.authoring.sources.labels",
    "semantic_ci_code.authoring.sources.commits",
    "semantic_ci_code.authoring.sources.merge",
    "semantic_ci_code.authoring.provenance",
)


def test_inv4_csci42_init_command_does_not_import_network_or_llm():
    closure = _transitive_closure("semantic_ci_code.cli.init_command")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
    assert not leaks, f"cli.init_command INV-4 violation: {leaks}"


def test_inv4_csci42_modules_do_not_import_network_or_llm():
    """Each Brief 8 CSCI-42 module (recipes + sources + provenance) must
    have a clean import closure. A single offender among them is enough
    to break INV-4, so this test enumerates them rather than relying on
    the package-level closure to surface a child.
    """
    failures: dict[str, list[str]] = {}
    for module in CSCI_42_MODULES:
        closure = _transitive_closure(module)
        leaks = sorted(m for m in closure if _is_forbidden_match(m, NETWORK_LLM_FORBIDDEN))
        if leaks:
            failures[module] = leaks
    assert not failures, f"CSCI-42 INV-4 violation: {failures}"


def test_inv4_csci42_modules_do_not_import_socket_or_ssl():
    """Stdlib network primitives are also forbidden — even without a
    high-level HTTP client, a `socket.create_connection` or
    `ssl.SSLContext` import would constitute a network surface.
    `importlib.metadata` is OK; that's how we read the package version.
    """
    forbidden_stdlib = ("socket", "ssl")
    failures: dict[str, list[str]] = {}
    for module in CSCI_42_MODULES:
        closure = _transitive_closure(module)
        leaks = sorted(m for m in closure if _is_forbidden_match(m, forbidden_stdlib))
        if leaks:
            failures[module] = leaks
    assert not failures, f"CSCI-42 stdlib network INV-4 violation: {failures}"


# ---------------------------------------------------------------------------
# INV-2 (CSCI-42 follow-up) — verdict-path handlers must NOT import the
# new init-recipe / authoring-sources modules either.
# ---------------------------------------------------------------------------


CSCI_42_FORBIDDEN_FOR_VERDICT_PATH = (
    "semantic_ci_code.cli.init_command",
    "semantic_ci_code.cli.init_recipes",
    "semantic_ci_code.authoring.sources",
    "semantic_ci_code.authoring.provenance",
)


def test_inv2_check_handler_does_not_import_init_recipe_or_sources():
    closure = _transitive_closure("semantic_ci_code.cli.commands.check")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, CSCI_42_FORBIDDEN_FOR_VERDICT_PATH))
    assert not leaks, f"cli.commands.check INV-2 violation (CSCI-42): {leaks}"


def test_inv2_compare_handler_does_not_import_init_recipe_or_sources():
    closure = _transitive_closure("semantic_ci_code.cli.commands.compare")
    leaks = sorted(m for m in closure if _is_forbidden_match(m, CSCI_42_FORBIDDEN_FOR_VERDICT_PATH))
    assert not leaks, f"cli.commands.compare INV-2 violation (CSCI-42): {leaks}"
