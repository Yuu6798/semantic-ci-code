from __future__ import annotations

import pytest

from semantic_ci_code.domain.state_schema import CodeState, EffectClass, EffectEntry
from semantic_ci_code.effects.effect_db import (
    EffectAccess,
    EffectMatch,
    EffectSignature,
    ResolutionLevel,
)
from semantic_ci_code.effects.python_effect_extractor import (
    default_python_effect_db,
    extract_python_effects,
)


def _by_resolved_call(entries: tuple[EffectEntry, ...]) -> dict[str, EffectEntry]:
    return {entry.evidence["resolved_call"]: entry for entry in _call_effects(entries)}


def _call_effects(entries: tuple[EffectEntry, ...]) -> tuple[EffectEntry, ...]:
    """Return only call-resolved effects, dropping global_mutation entries.

    Alias-shadowing assertions pre-date the global_mutation pass and
    were written against ``entries == ()`` to mean "no call resolved".
    Module reassignments now legitimately produce additional entries
    on the same fixtures, so the call assertions filter through this.
    """
    return tuple(e for e in entries if e.effect_class is not EffectClass.GLOBAL_MUTATION)


def _resolved_calls(entries: tuple[EffectEntry, ...]) -> set[str]:
    return {entry.evidence["resolved_call"] for entry in _call_effects(entries)}


def test_default_python_effect_db_loads():
    signatures = default_python_effect_db()
    assert any(s.match.call == "open" for s in signatures)
    assert any(s.match.call == "subprocess.run" for s in signatures)


def test_extracts_required_direct_calls():
    source = """
import os
import subprocess
import urllib.request

open("a.txt")
print("hello")
eval("1 + 1")
os.remove("b.txt")
subprocess.run(["ls"])
urllib.request.urlopen("https://example.com")
""".lstrip()

    entries = extract_python_effects(source, filename="sample.py")

    assert {entry.fqn for entry in entries} == {"<module>"}
    assert _resolved_calls(entries) == {
        "open",
        "print",
        "eval",
        "os.remove",
        "subprocess.run",
        "urllib.request.urlopen",
    }


def test_evidence_payload_is_complete():
    source = "open('a.txt')\n"

    entries = extract_python_effects(source, filename="sample.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.confidence == 1.0
    assert entry.effect_class is EffectClass.FS
    assert entry.evidence == {
        "raw_call": "open",
        "resolved_call": "open",
        "file": "sample.py",
        "line": 1,
        "resolution_level": ResolutionLevel.DIRECT_CALL.value,
    }


def test_line_numbers_are_recorded():
    source = "x = 1\n\nprint('hi')\n"

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].evidence["line"] == 3


def test_unknown_call_is_ignored():
    source = """
def helper():
    return 1

helper()
my_module.do_thing(1, 2)
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert entries == ()


def test_method_call_on_instance_is_not_resolved_in_p1():
    # P2/P3 territory: ``Path("x").write_text(...)`` and ``p.write_text(...)``
    # are method calls on instances and must not match the direct-call path.
    source = """
from pathlib import Path

Path("x").write_text("hello")
p = Path("x")
p.write_text("hello")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert all(entry.fqn != "pathlib.Path.write_text" for entry in entries)
    assert entries == ()


def test_imported_alias_resolves_module_alias():
    source = """
import os as operating_system
operating_system.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.effect_class is EffectClass.FS
    assert entry.evidence["raw_call"] == "operating_system.remove"
    assert entry.evidence["resolved_call"] == "os.remove"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_imported_alias_resolves_short_module_alias():
    source = """
import subprocess as sp
sp.run(["ls"])
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "sp.run"
    assert entry.evidence["resolved_call"] == "subprocess.run"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_imported_alias_resolves_dotted_module_alias():
    source = """
import urllib.request as request
request.urlopen("https://example.com")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "request.urlopen"
    assert entry.evidence["resolved_call"] == "urllib.request.urlopen"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_from_import_resolves_callable_name():
    source = """
from os import remove
remove("a.txt")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "remove"
    assert entry.evidence["resolved_call"] == "os.remove"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_from_import_resolves_aliased_callable():
    source = """
from os import remove as rm
rm("a.txt")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "rm"
    assert entry.evidence["resolved_call"] == "os.remove"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_from_dotted_module_resolves_callable():
    source = """
from urllib.request import urlopen
urlopen("https://example.com")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "urlopen"
    assert entry.evidence["resolved_call"] == "urllib.request.urlopen"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_from_dotted_module_resolves_aliased_callable():
    source = """
from urllib.request import urlopen as fetch
fetch("https://example.com")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "fetch"
    assert entry.evidence["resolved_call"] == "urllib.request.urlopen"
    assert entry.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_direct_call_after_plain_import_keeps_direct_call_level():
    source = """
import os
os.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "<module>"
    assert entry.evidence["raw_call"] == "os.remove"
    assert entry.evidence["resolved_call"] == "os.remove"
    assert entry.evidence["resolution_level"] == ResolutionLevel.DIRECT_CALL.value


def test_star_import_is_not_resolved():
    source = """
from os import *

remove("a.txt")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert entries == ()


def test_relative_import_is_not_resolved():
    source = """
from . import remove

remove("a.txt")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert entries == ()


def test_alias_shadowed_by_module_level_assignment_is_not_resolved():
    # Module-level reassignment of the alias name conservatively drops
    # the alias from resolution for the entire module, regardless of
    # source order. The reassignment itself is an independent
    # global_mutation; this test focuses on call effects.
    source = """
from os import remove as rm
rm = lambda x: None
rm("a.txt")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_even_for_calls_before_assignment():
    # Brief: P1 does not track module-level statement order for alias
    # resolution. A later assignment shadows the alias for earlier
    # calls too. The reassignment is reported as global_mutation; this
    # test focuses on call effects.
    source = """
import os as op
op.remove("first")
op = 5
op.remove("second")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_by_assignment_inside_if():
    source = """
import os as op
if True:
    op = lambda x: None
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_by_assignment_inside_else():
    source = """
import os as op
if False:
    pass
else:
    op = lambda x: None
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_by_assignment_inside_try_or_except():
    source = """
import os as op
try:
    op = lambda x: None
except Exception:
    pass
op.remove("a")
""".lstrip()
    assert _call_effects(extract_python_effects(source, filename="m.py")) == ()

    source = """
import os as op
try:
    pass
except Exception as op:
    pass
op.remove("a")
""".lstrip()
    assert _call_effects(extract_python_effects(source, filename="m.py")) == ()


def test_alias_shadowed_by_for_loop_target():
    source = """
import os as op
for op in [1, 2, 3]:
    pass
op.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert entries == ()


def test_alias_shadowed_by_assignment_inside_for_body():
    source = """
import os as op
for _ in [1, 2, 3]:
    op = 5
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_by_assignment_inside_while():
    source = """
import os as op
while False:
    op = 5
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_alias_shadowed_by_with_as_binding():
    source = """
import os as op
with open("/tmp/x") as op:
    pass
op.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    # The ``open(...)`` call inside the with-statement still produces
    # an open() detection, so we only assert that the aliased call is
    # gone.
    assert all(entry.evidence["raw_call"] != "op.remove" for entry in entries)
    assert "os.remove" not in _resolved_calls(entries)


def test_alias_shadowed_by_nested_compound_statement():
    source = """
import os as op
if True:
    if True:
        for _ in [0]:
            op = 5
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_function_local_assignment_does_not_shadow_module_alias():
    # Brief: only module-level simple assignments shadow. A function-
    # local rebinding of the alias name does not affect module-level
    # alias resolution.
    source = """
import os as op

def helper():
    op = 5
    return op

op.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "<module>"
    assert entries[0].evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_annotation_only_does_not_shadow_alias():
    # ``op: int`` annotates without rebinding. Suppressing detection
    # in that case would be a false negative, so the alias survives.
    source = """
import os as op
op: int
op.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "<module>"
    assert entries[0].evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value


def test_annotated_assignment_with_value_shadows_alias():
    source = """
import os as op
op: int = 5
op.remove("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_aug_assign_shadows_alias():
    source = """
from os import remove as rm
rm += 1
rm("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_tuple_unpacking_at_module_level_shadows_alias():
    source = """
from os import remove as rm
rm, _ = (lambda x: None, None)
rm("a")
""".lstrip()

    entries = _call_effects(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_aliased_extraction_assignable_to_code_state():
    source = """
from os import remove as rm
import subprocess as sp

rm("a.txt")
sp.run(["ls"])
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")
    state = CodeState(effects=entries)

    assert {e.fqn for e in state.effects} == {"<module>"}
    assert _resolved_calls(state.effects) == {"os.remove", "subprocess.run"}
    assert all(
        e.evidence["resolution_level"] == ResolutionLevel.IMPORTED_ALIAS.value
        for e in state.effects
    )


def test_syntax_error_propagates_as_syntax_error():
    with pytest.raises(SyntaxError):
        extract_python_effects("def broken(:\n", filename="bad.py")


def test_result_is_assignable_to_code_state_effects():
    source = "print('x')\nopen('y')\n"

    entries = extract_python_effects(source, filename="m.py")
    state = CodeState(effects=entries)

    assert len(state.effects) == 2
    assert {e.effect_class for e in state.effects} == {
        EffectClass.STDOUT,
        EffectClass.FS,
    }


def test_extractor_accepts_custom_db_and_pins_first_match_for_duplicates():
    custom_db = (
        EffectSignature(
            id="open_first",
            language="python",
            match=EffectMatch(call="open"),
            effect=EffectClass.FS,
            access=EffectAccess.READ,
            severity="medium",
        ),
        EffectSignature(
            id="open_second",
            language="python",
            match=EffectMatch(call="open"),
            effect=EffectClass.IO,
            access=EffectAccess.WRITE,
            severity="high",
        ),
    )

    entries = extract_python_effects("open('a')\n", filename="m.py", db=custom_db)

    assert len(entries) == 1
    # Duplicate ``match.call``: the first declared signature wins.
    assert entries[0].effect_class is EffectClass.FS


def test_extractor_with_empty_db_emits_nothing():
    entries = extract_python_effects("open('a')\nprint('b')\n", filename="m.py", db=())
    assert entries == ()


def test_dynamic_code_and_unsafe_deserialize_are_detected():
    source = """
import importlib
import pickle

eval("1+1")
exec("pass")
compile("x", "<m>", "exec")
__import__("os")
importlib.import_module("os")

pickle.loads(b"")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")
    by_class: dict[EffectClass, list[str]] = {}
    for entry in entries:
        by_class.setdefault(entry.effect_class, []).append(entry.evidence["resolved_call"])

    assert set(by_class[EffectClass.DYNAMIC_CODE]) == {
        "eval",
        "exec",
        "compile",
        "__import__",
        "importlib.import_module",
    }
    assert set(by_class[EffectClass.UNSAFE_DESERIALIZE]) == {"pickle.loads"}


def test_call_with_non_name_root_is_skipped():
    # ``factory()()`` — the func is a Call, not a Name/Attribute chain.
    source = "factory()(1, 2)\n"
    entries = extract_python_effects(source, filename="m.py")
    assert entries == ()


def test_repeated_call_emits_one_entry_per_occurrence():
    source = "print('a')\nprint('b')\nprint('c')\n"
    entries = extract_python_effects(source, filename="m.py")
    assert [e.evidence["line"] for e in entries] == [1, 2, 3]
    assert {e.fqn for e in entries} == {"<module>"}
    assert _resolved_calls(entries) == {"print"}


def test_entries_record_dotted_fqn_for_attribute_calls():
    source = "import os\nos.remove('a')\n"
    entries = extract_python_effects(source, filename="m.py")
    by_call = _by_resolved_call(entries)
    assert by_call["os.remove"].fqn == "<module>"
    assert by_call["os.remove"].evidence["resolution_level"] == "direct_call"


def test_nested_calls_are_each_detected():
    source = "print(open('a.txt'))\n"
    entries = extract_python_effects(source, filename="m.py")
    resolved_calls = [entry.evidence["resolved_call"] for entry in entries]
    assert sorted(resolved_calls) == ["open", "print"]
    assert {entry.fqn for entry in entries} == {"<module>"}


def test_extractor_ignores_non_python_signatures():
    # A multi-language DB may declare a foreign signature for a call name
    # that also exists in Python. The Python extractor must skip the
    # foreign entry even when it is declared first.
    mixed_db = (
        EffectSignature(
            id="ts_console_log",
            language="typescript",
            match=EffectMatch(call="print"),
            effect=EffectClass.NET,
            access=EffectAccess.WRITE,
            severity="high",
        ),
        EffectSignature(
            id="py_print",
            language="python",
            match=EffectMatch(call="print"),
            effect=EffectClass.STDOUT,
            access=EffectAccess.WRITE,
            severity="low",
        ),
    )

    entries = extract_python_effects("print('hi')\n", filename="m.py", db=mixed_db)

    assert len(entries) == 1
    assert entries[0].effect_class is EffectClass.STDOUT


def test_extractor_skips_calls_only_present_in_non_python_signatures():
    foreign_only_db = (
        EffectSignature(
            id="ts_print",
            language="typescript",
            match=EffectMatch(call="print"),
            effect=EffectClass.STDOUT,
            access=EffectAccess.WRITE,
            severity="low",
        ),
    )

    entries = extract_python_effects("print('hi')\n", filename="m.py", db=foreign_only_db)

    assert entries == ()


def test_call_effect_fqn_uses_module_for_module_level_call():
    entries = extract_python_effects("print('module')\n", filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "<module>"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effect_fqn_uses_enclosing_function_name():
    source = """
def run():
    print("function")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "run"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effect_fqn_uses_module_prefix_when_provided():
    source = """
def run():
    print("function")
""".lstrip()

    entries = extract_python_effects(source, filename="pkg/a.py", module_fqn="pkg.a")

    assert len(entries) == 1
    assert entries[0].fqn == "pkg.a.run"
    assert entries[0].evidence["resolved_call"] == "print"


def test_module_level_call_effect_fqn_uses_module_prefix_when_provided():
    entries = extract_python_effects(
        "print('module')\n",
        filename="pkg/a.py",
        module_fqn="pkg.a",
    )

    assert len(entries) == 1
    assert entries[0].fqn == "pkg.a"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effect_fqn_uses_enclosing_method_name():
    source = """
class Worker:
    def run(self):
        print("method")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "Worker.run"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effect_fqn_uses_nested_function_name():
    source = """
def outer():
    def inner():
        print("nested")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "outer.inner"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effects_can_be_grouped_by_enclosing_fqn():
    source = """
def alpha():
    print("alpha")
    open("alpha.txt")

def beta():
    print("beta")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")
    by_fqn: dict[str, set[str]] = {}
    for entry in entries:
        by_fqn.setdefault(entry.fqn, set()).add(entry.evidence["resolved_call"])

    assert by_fqn == {
        "alpha": {"print", "open"},
        "beta": {"print"},
    }


def test_call_effect_fqn_uses_lambda_scope():
    source = "handler = lambda: print('lambda')\n"

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "<lambda>"
    assert entries[0].evidence["resolved_call"] == "print"


def test_call_effect_fqn_preserves_outer_scope_for_nested_lambdas():
    source = """
def alpha():
    return lambda: print("alpha")

def beta():
    return lambda: print("beta")
""".lstrip()

    entries = extract_python_effects(source, filename="pkg/m.py", module_fqn="pkg.m")
    effects = {(entry.fqn, entry.evidence["resolved_call"]) for entry in entries}

    assert effects == {
        ("pkg.m.alpha.<lambda>", "print"),
        ("pkg.m.beta.<lambda>", "print"),
    }


def test_comprehension_call_inherits_enclosing_function_scope():
    source = """
def run(items):
    return [print(item) for item in items]
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    assert len(entries) == 1
    assert entries[0].fqn == "run"
    assert entries[0].evidence["resolved_call"] == "print"


# --------------------------------------------------------------------- #
# global_mutation extraction
# --------------------------------------------------------------------- #


def _global_mutations(entries: tuple[EffectEntry, ...]) -> tuple[EffectEntry, ...]:
    return tuple(e for e in entries if e.effect_class is EffectClass.GLOBAL_MUTATION)


def test_global_statement_in_function_body_is_detected():
    source = """
def f():
    global g
    g = 1
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "global:g"
    assert entry.confidence == 1.0
    assert entry.evidence == {
        "mutation_kind": "global_declaration",
        "target": "g",
        "file": "m.py",
        "line": 2,
        "resolution_level": ResolutionLevel.STATEMENT_LEVEL.value,
    }


def test_global_statement_emits_one_entry_per_name():
    source = """
def f():
    global a, b, c
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert {e.fqn for e in entries} == {"global:a", "global:b", "global:c"}
    assert all(e.evidence["mutation_kind"] == "global_declaration" for e in entries)


def test_nonlocal_statement_in_nested_function_is_detected():
    source = """
def outer():
    n = 1
    def inner():
        nonlocal n
        n = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "nonlocal:n"
    assert entry.evidence["mutation_kind"] == "nonlocal_declaration"
    assert entry.evidence["resolution_level"] == ResolutionLevel.STATEMENT_LEVEL.value


def test_module_level_reassignment_emits_for_subsequent_bindings():
    source = """
x = 1
x = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "module:x"
    assert entry.evidence["mutation_kind"] == "module_reassignment"
    assert entry.evidence["target"] == "x"
    assert entry.evidence["line"] == 2


def test_module_level_aug_assign_after_initial_binding_emits():
    source = """
x = 1
x += 1
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"
    assert entries[0].evidence["line"] == 2


def test_module_level_annotated_then_reassigned_emits():
    source = """
x: int = 1
x = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"
    assert entries[0].evidence["mutation_kind"] == "module_reassignment"


def test_module_level_initial_binding_alone_is_not_emitted():
    source = "CONSTANT = 1\n"

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_module_level_subscript_assign_is_detected():
    source = """
CONFIG = {}
CONFIG["debug"] = True
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    # CONFIG = {} is the first binding (no emit), the subscript write
    # always emits.
    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "module:CONFIG"
    assert entry.evidence["mutation_kind"] == "module_subscript_assign"
    assert entry.evidence["target"] == "CONFIG"
    assert entry.evidence["line"] == 2


def test_module_level_attribute_assign_is_detected():
    source = "settings.value = 1\n"

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "module:settings"
    assert entry.evidence["mutation_kind"] == "module_attribute_assign"
    assert entry.evidence["target"] == "settings"
    assert entry.evidence["line"] == 1


def test_method_call_mutations_are_not_detected_in_p1():
    # ``items.append(1)`` is a method call mutation; brief defers it to P2+.
    source = """
items = []
items.append(1)
data.update({"k": "v"})
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_imports_alone_do_not_emit_global_mutation():
    source = """
import os
from typing import Any
from .relmod import helper
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_reassigning_imported_name_emits_module_reassignment():
    source = """
import os
os = object()
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:os"
    assert entries[0].evidence["mutation_kind"] == "module_reassignment"


def test_reassigning_relative_imported_name_emits_module_reassignment():
    for source in (
        """
from .config import settings
settings = object()
""".lstrip(),
        """
from . import settings
settings = object()
""".lstrip(),
    ):
        entries = _global_mutations(extract_python_effects(source, filename="pkg/mod.py"))

        assert len(entries) == 1
        assert entries[0].fqn == "module:settings"
        assert entries[0].evidence["mutation_kind"] == "module_reassignment"


def test_class_body_assignment_is_not_module_mutation():
    source = """
class Foo:
    a = 1
    a = 2
    b: int = 3
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_function_local_assignment_is_not_module_mutation():
    source = """
def f():
    x = 1
    x = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_function_body_global_with_assignment_emits_only_global_declaration():
    source = """
g = 0
def f():
    global g
    g = 1
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert {e.fqn for e in entries} == {"global:g"}


def test_module_reassignment_inside_if_is_detected():
    source = """
x = 1
if cond:
    x = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"
    assert entries[0].evidence["line"] == 3


def test_module_reassignment_inside_for_loop_body_is_detected():
    source = """
x = 1
for _ in range(3):
    x = 2
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"


def test_module_level_delete_of_name_after_binding_emits():
    source = """
x = 1
del x
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "module:x"
    assert entry.evidence["mutation_kind"] == "module_delete"


def test_module_level_delete_of_subscript_emits():
    source = """
CONFIG = {}
del CONFIG["debug"]
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    entry = entries[0]
    assert entry.fqn == "module:CONFIG"
    assert entry.evidence["mutation_kind"] == "module_subscript_delete"


def test_annotation_only_assignment_does_not_emit_global_mutation():
    source = """
x: int = 1
y: int
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    # x: int = 1 is a first binding (no emit). y: int has no value, so it
    # neither binds nor emits.
    assert entries == ()


def test_tuple_unpacking_module_reassignment_emits_per_name():
    source = """
x = 1
y = 2
x, y = 3, 4
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    fqns = {e.fqn for e in entries}
    assert fqns == {"module:x", "module:y"}
    assert all(e.evidence["mutation_kind"] == "module_reassignment" for e in entries)


def test_subscript_with_non_name_root_is_not_emitted():
    # ``factory()["x"] = 1`` — no stable base name to attribute the
    # mutation to.
    source = "factory()['x'] = 1\n"

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert entries == ()


def test_global_mutation_coexists_with_call_effects():
    source = """
import os as op

CONFIG = {}
CONFIG["debug"] = True

x = 1
x = 2

op.remove("a")
print("hi")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")
    by_class: dict[EffectClass, list[str]] = {}
    for e in entries:
        by_class.setdefault(e.effect_class, []).append(e.fqn)

    assert set(by_class[EffectClass.GLOBAL_MUTATION]) == {"module:CONFIG", "module:x"}
    assert any(
        e.effect_class is EffectClass.FS and e.evidence.get("resolved_call") == "os.remove"
        for e in entries
    )
    assert any(
        e.effect_class is EffectClass.STDOUT and e.evidence.get("resolved_call") == "print"
        for e in entries
    )


def test_global_mutation_results_assignable_to_code_state():
    source = """
def f():
    global g
    g = 1

x = 1
x = 2
CONFIG = {}
CONFIG["k"] = 1
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")
    state = CodeState(effects=entries)

    mutation_fqns = {e.fqn for e in state.effects if e.effect_class is EffectClass.GLOBAL_MUTATION}
    assert mutation_fqns == {"global:g", "module:x", "module:CONFIG"}


def test_global_mutation_existing_call_tests_unaffected_by_filter():
    # Sanity: extracting from a source that has only call effects yields
    # zero global_mutation entries.
    source = "open('a')\nprint('b')\n"

    mutations = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert mutations == ()


def test_try_star_body_assignments_are_tracked():
    # ``except*`` (PEP 654, Python 3.11+) uses ast.TryStar, not ast.Try.
    # Both passes — module_scope shadowing for alias resolution and
    # module_scope binding events for global_mutation — must traverse
    # TryStar bodies the same way they traverse Try bodies.
    source = """
import os as op
x = 1
try:
    pass
except* ValueError:
    x = 2
    op = 5
op.remove("a")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    # alias ``op`` is shadowed by the assignment inside except* body, so
    # the call must NOT resolve as imported_alias.
    assert _call_effects(entries) == ()

    # ``x = 2`` and ``op = 5`` inside except* body are module-scope
    # rebinds and must be reported as module_reassignment.
    mutations = _global_mutations(entries)
    fqns = {(e.fqn, e.evidence["mutation_kind"]) for e in mutations}
    assert ("module:x", "module_reassignment") in fqns
    assert ("module:op", "module_reassignment") in fqns


def test_try_star_handler_as_binding_shadows_alias():
    source = """
import os as op
try:
    pass
except* Exception as op:
    pass
op.remove("a")
""".lstrip()

    assert _call_effects(extract_python_effects(source, filename="m.py")) == ()


def test_except_handler_as_binding_emits_module_reassignment():
    source = """
x = 1
try:
    1 / 0
except Exception as x:
    pass
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"
    assert entries[0].evidence["mutation_kind"] == "module_reassignment"
    assert entries[0].evidence["line"] == 4


def test_try_star_handler_as_binding_emits_module_reassignment():
    source = """
x = 1
try:
    pass
except* Exception as x:
    pass
""".lstrip()

    entries = _global_mutations(extract_python_effects(source, filename="m.py"))

    assert len(entries) == 1
    assert entries[0].fqn == "module:x"
    assert entries[0].evidence["mutation_kind"] == "module_reassignment"
    assert entries[0].evidence["line"] == 4
