from __future__ import annotations

_ANSI = {
    "red": "\x1b[31m",
    "yellow": "\x1b[33m",
    "green": "\x1b[32m",
    "cyan": "\x1b[36m",
    "gray": "\x1b[90m",
    "reset": "\x1b[0m",
}


def colored(text: str, color: str, *, enabled: bool) -> str:
    if not enabled or color not in _ANSI:
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"
