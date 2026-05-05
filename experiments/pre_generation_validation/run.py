#!/usr/bin/env python3
"""Pre-generation validation reproduction (self-contained).

Verifies that semantic-ci's engine accepts virtual / stub-only candidates,
satisfying the §23.1 input contract regardless of state provenance.

Three cases run on a synthetic ~25-line baseline package (tinypkg/):

    F1_pass        stub adds both required functions      -> verdict pass
    F2_missing     stub adds only one required function   -> verdict fail
    F3_collateral  stub satisfies additions but           -> verdict fail
                   privatizes existing Counter.increment

All candidates contain only API stubs with NotImplementedError bodies.
The script uses tempfile.TemporaryDirectory and leaves no artifacts.

Run:
    python experiments/pre_generation_validation/run.py

Exit code is 0 when 3/3 verdicts match expectation, 1 otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline"

STUB_FULL = '''\
"""Stub: predicted persistence helpers for tinypkg.Counter."""
from tinypkg.counter import Counter


def save_counter(counter: Counter, path: str) -> None:
    """Persist counter state to path."""
    raise NotImplementedError("pre-generation stub")


def load_counter(path: str) -> Counter:
    """Restore counter state from path."""
    raise NotImplementedError("pre-generation stub")
'''

STUB_PARTIAL = '''\
"""Stub: plan declares only save, forgot load."""
from tinypkg.counter import Counter


def save_counter(counter: Counter, path: str) -> None:
    """Persist counter state to path."""
    raise NotImplementedError("pre-generation stub")
'''

TARGET_YAML = """\
intent: add public save/load helpers for Counter persistence
change:
  primary_kind: feature
constraints:
  - id: save_counter_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_any
    expected:
      - fqn: persistence.save_counter
        kind: function
        signature: |-
          def save_counter(counter: Counter, path: str) -> None:
              ...
        visibility: public
  - id: load_counter_added
    kind: delta
    target: api_surface_delta.added
    operator: includes_any
    expected:
      - fqn: persistence.load_counter
        kind: function
        signature: |-
          def load_counter(path: str) -> Counter:
              ...
        visibility: public
"""


def patch_add_full_stub(pkg: Path) -> None:
    (pkg / "tinypkg" / "persistence.py").write_text(STUB_FULL)


def patch_add_partial_stub(pkg: Path) -> None:
    (pkg / "tinypkg" / "persistence.py").write_text(STUB_PARTIAL)


def patch_privatize_increment(pkg: Path) -> None:
    counter_py = pkg / "tinypkg" / "counter.py"
    text = counter_py.read_text()
    text = text.replace(
        "    def increment(self, by: int = 1) -> int:",
        "    def _bump(self, by: int = 1) -> int:",
    )
    counter_py.write_text(text)


@dataclass
class Case:
    name: str
    description: str
    patches: list[Callable[[Path], None]]
    expected: str


CASES: list[Case] = [
    Case(
        "F1_pass",
        "Stub declares both required additions",
        [patch_add_full_stub],
        "pass",
    ),
    Case(
        "F2_missing",
        "Stub omits load_counter required by intent",
        [patch_add_partial_stub],
        "fail",
    ),
    Case(
        "F3_collateral",
        "Stub satisfies additions but privatizes Counter.increment",
        [patch_add_full_stub, patch_privatize_increment],
        "fail",
    ),
]


def run_compare(baseline: Path, candidate: Path, target: Path) -> dict:
    proc = subprocess.run(
        [
            "semantic-ci",
            "compare",
            "--baseline-dir",
            str(baseline),
            "--candidate-dir",
            str(candidate),
            "--package-root-baseline",
            str(baseline / "tinypkg"),
            "--package-root-candidate",
            str(candidate / "tinypkg"),
            "--target",
            str(target),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(proc.stdout) if proc.stdout else {}
    except json.JSONDecodeError:
        return {
            "verdict": "error",
            "stderr": (proc.stderr or proc.stdout)[:300],
        }
    return {
        "verdict": data.get("verdict"),
        "exit_code": proc.returncode,
        "violations": data.get("summary", {}).get("fix_required", 0),
        "satisfied": data.get("summary", {}).get("satisfied", 0),
        "constraints": [
            {"id": r["constraint_id"], "status": r["status"]} for r in data.get("results", [])
        ],
    }


def main() -> int:
    if not BASELINE.exists():
        print(f"baseline missing: {BASELINE}", file=sys.stderr)
        return 2

    rows: list[tuple[Case, dict]] = []
    with tempfile.TemporaryDirectory(prefix="pregen_") as tmp:
        tmp_root = Path(tmp)
        for case in CASES:
            cand = tmp_root / case.name / "candidate"
            shutil.copytree(BASELINE, cand)
            for patch in case.patches:
                patch(cand)
            target = tmp_root / case.name / "target.yaml"
            target.write_text(TARGET_YAML)
            outcome = run_compare(BASELINE, cand, target)
            rows.append((case, outcome))

    print(f"{'case':<18} {'expected':<10} {'verdict':<10} {'violns':<8} {'sat':<6} {'match':<6}")
    print("-" * 60)
    correct = 0
    for case, outcome in rows:
        ok = outcome.get("verdict") == case.expected
        correct += int(ok)
        print(
            f"{case.name:<18} {case.expected:<10} "
            f"{str(outcome.get('verdict')):<10} "
            f"{str(outcome.get('violations', '?')):<8} "
            f"{str(outcome.get('satisfied', '?')):<6} "
            f"{('PASS' if ok else 'MISS'):<6}"
        )
    print(f"\n{correct}/{len(rows)} verdicts matched expectation")

    if correct < len(rows):
        for case, outcome in rows:
            print(f"\n[{case.name}] {case.description}")
            for c in outcome.get("constraints", []):
                mark = "FAIL" if c["status"] == "violated" else "ok  "
                print(f"  [{mark}] {c['id']}")
            if "stderr" in outcome:
                print(f"  stderr: {outcome['stderr']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
