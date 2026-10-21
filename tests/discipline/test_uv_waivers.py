"""``[tool.uv.exclude-newer-package]`` の期限切れ waiver を検出する。

``exclude-newer = "7 days"`` は相対窓だが、``exclude-newer-package`` の値は絶対日時。
絶対日時の waiver はグローバルの 7 日窓より長く生き残り、その package を黙って凍結し続ける。
そのため失効は静かに放置せず、14 日超過でテストを失敗させて大きく知らせる。
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime, timedelta

from ._helpers import REPO_ROOT

MAX_WAIVER_AGE = timedelta(days=14)


def expired_waivers(pyproject_text: str, now: datetime) -> dict[str, datetime]:
    """Return waivers whose absolute UTC timestamp is older than ``MAX_WAIVER_AGE``."""

    waivers = tomllib.loads(pyproject_text).get("tool", {}).get("uv", {})
    expired: dict[str, datetime] = {}
    for package, raw in waivers.get("exclude-newer-package", {}).items():
        stamp = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
        assert stamp.tzinfo is not None, f"{package}: waiver は UTC の絶対日時（例: ...Z）で書く"
        if now - stamp.astimezone(UTC) > MAX_WAIVER_AGE:
            expired[package] = stamp
    return expired


def test_uv_exclude_newer_package_waivers_have_not_expired() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    expired = expired_waivers(text, datetime.now(UTC))
    assert not expired, (
        "pyproject.toml の [tool.uv] exclude-newer-package waiver が 14 日を超過しました: "
        + ", ".join(f"{pkg} ({stamp.isoformat()})" for pkg, stamp in expired.items())
        + "\n該当行（と直上のコメント）を削除して `uv lock` を実行してください。"
    )


def test_expired_waiver_detector_flags_old_and_keeps_fresh() -> None:
    text = (
        "[tool.uv.exclude-newer-package]\n"
        'old = "2026-01-01T00:00:00Z"\n'
        'fresh = "2026-01-10T00:00:00Z"\n'
    )
    assert expired_waivers(text, datetime(2026, 1, 20, tzinfo=UTC)).keys() == {"old"}
    assert not expired_waivers("[tool.uv]\n", datetime(2026, 1, 20, tzinfo=UTC))
