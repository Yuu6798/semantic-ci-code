"""Semantic CI Code Edition."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("semantic-ci-code")
except PackageNotFoundError:
    __version__ = "0.0.0"
