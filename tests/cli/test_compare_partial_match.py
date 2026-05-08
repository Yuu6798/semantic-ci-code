from __future__ import annotations

from pathlib import Path

from .helpers import payload, run_semantic_ci

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compare"
BASELINE = FIXTURES / "baseline_pkg"
CANDIDATE = FIXTURES / "candidate_pkg"


def test_compare_excludes_all_partial_dict_blocks_added_api(tmp_path: Path):
    target = tmp_path / "target.yaml"
    target.write_text(
        """
intent: forbid added API
change:
  primary_kind: feature
constraints:
  - id: forbid_added
    kind: delta
    target: api_surface_delta.added
    operator: excludes_all
    expected:
      - fqn: mod.added
""",
        encoding="utf-8",
    )

    result = run_semantic_ci(
        Path.cwd(),
        "compare",
        "--baseline-dir",
        str(BASELINE),
        "--candidate-dir",
        str(CANDIDATE),
        "--target",
        str(target),
        "--format",
        "json",
    )
    data = payload(result)
    forbid_result = next(
        item for item in data["results"] if item["constraint_id"] == "forbid_added"
    )

    assert result.returncode == 1
    assert data["verdict"] == "fail"
    assert forbid_result["status"] == "violated"
    assert forbid_result["evidence"]["matched"] == [
        {
            "expected_item": {"fqn": "mod.added"},
            "observed_record": {
                "fqn": "mod.added",
                "kind": "function",
                "signature": "def added() -> int:\n    ...",
                "visibility": "public",
            },
        }
    ]
