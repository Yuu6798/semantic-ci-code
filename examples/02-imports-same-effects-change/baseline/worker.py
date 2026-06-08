import subprocess  # noqa: S404 - intentional runnable example fixture

_SUBPROCESS_MODULE = subprocess.__name__


def render_status(name: str) -> str:
    return f"ready:{name}:{_SUBPROCESS_MODULE}"
