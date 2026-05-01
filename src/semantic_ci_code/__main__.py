from __future__ import annotations

from .scope import default_scope


def main() -> None:
    """Print the current project scope as JSON."""
    print(default_scope().model_dump_json(indent=2))


if __name__ == "__main__":
    main()
