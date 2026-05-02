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


def _by_fqn(entries: tuple[EffectEntry, ...]) -> dict[str, EffectEntry]:
    return {entry.fqn: entry for entry in entries}


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
    fqns = {entry.fqn for entry in entries}

    assert fqns == {
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
        "call": "open",
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


def test_imported_alias_is_not_resolved_in_p1():
    source = """
from os import remove as rm
rm("a.txt")
""".lstrip()

    entries = extract_python_effects(source, filename="m.py")

    # The DB does not contain a bare ``rm`` entry, and P1 does not perform
    # alias resolution, so nothing is detected.
    assert entries == ()


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
        by_class.setdefault(entry.effect_class, []).append(entry.fqn)

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
    assert {e.fqn for e in entries} == {"print"}


def test_entries_record_dotted_fqn_for_attribute_calls():
    source = "import os\nos.remove('a')\n"
    entries = extract_python_effects(source, filename="m.py")
    by_fqn = _by_fqn(entries)
    assert "os.remove" in by_fqn
    assert by_fqn["os.remove"].evidence["resolution_level"] == "direct_call"
