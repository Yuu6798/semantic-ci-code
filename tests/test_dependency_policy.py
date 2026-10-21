"""依存 waiver の期限管理: pyproject の ``[tool.dependency-waivers]`` を検証する。

``[tool.uv] exclude-newer-package`` の waiver は絶対日時で、グローバルの 7 日窓より長く
生き残りその package を黙って凍結する。各 waiver に期限を必須とし、超過を CI 赤で知らせる。
"""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
FIX = (
    "pyproject の [tool.uv.exclude-newer-package] と [tool.dependency-waivers] "
    "から削除して `uv lock`"
)


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value).date()


def waiver_problems(
    waivers: dict[str, object], deadlines: dict[str, date | datetime | str], today: date
) -> list[str]:
    """Return one message per waiver/deadline inconsistency (empty list = healthy)."""

    problems = [f"{pkg}: waiver に期限が無い" for pkg in sorted(waivers) if pkg not in deadlines]
    problems += [
        f"{pkg}: 期限だけが残っている（waiver は削除済み）"
        for pkg in sorted(deadlines)
        if pkg not in waivers
    ]
    problems += [
        f"{pkg}: 期限 {_as_date(deadlines[pkg])} を超過"
        for pkg in sorted(deadlines)
        if _as_date(deadlines[pkg]) < today
    ]
    return problems


def test_dependency_waivers_have_deadlines_and_are_not_expired() -> None:
    tool = tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get("tool", {})
    waivers = tool.get("uv", {}).get("exclude-newer-package", {})
    problems = waiver_problems(
        waivers, tool.get("dependency-waivers", {}), datetime.now(UTC).date()
    )
    assert not problems, (
        "依存 waiver の期限管理に問題があります:\n" + "\n".join(problems) + f"\n対応: {FIX}"
    )


def test_waiver_problems_reports_missing_stale_and_expired() -> None:
    today = date(2026, 11, 1)
    waivers = {"nodeadline": "2026-10-20T03:00:00Z", "expired": "2026-10-20T03:00:00Z", "ok": "x"}
    deadlines = {"expired": date(2026, 10, 31), "ok": "2026-11-01", "stale": datetime(2026, 12, 1)}
    assert [p.split(":")[0] for p in waiver_problems(waivers, deadlines, today)] == [
        "nodeadline",
        "stale",
        "expired",
    ]
    assert waiver_problems({}, {}, today) == []
