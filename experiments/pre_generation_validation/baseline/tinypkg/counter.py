"""Minimal counter package — the existing public API of tinypkg."""


class Counter:
    """Track an integer count in memory."""

    def __init__(self, start: int = 0) -> None:
        self._value = start

    def increment(self, by: int = 1) -> int:
        """Add ``by`` to the count and return the new value."""
        self._value += by
        return self._value

    def value(self) -> int:
        """Return the current count."""
        return self._value
