from __future__ import annotations

from pathlib import Path

import pytest

from semantic_ci_code.cli.doctor_support import PackageRootError, resolve_package_root


def test_resolve_package_root_default_dot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    assert resolve_package_root(None) == tmp_path.resolve()


def test_resolve_package_root_rejects_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PackageRootError):
        resolve_package_root(str(tmp_path.resolve()))


def test_resolve_package_root_rejects_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PackageRootError):
        resolve_package_root("../outside")


def test_resolve_package_root_rejects_nonexistent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PackageRootError):
        resolve_package_root("nonexistent_dir")
