import json
import os as os


def existing(value: int, extra: int = 0) -> int:
    print("candidate")
    if extra:
        return value + extra
    return value


def added() -> str:
    return json.dumps({"ok": True})
