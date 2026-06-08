import subprocess  # noqa: S404 - intentional runnable example fixture

_SUBPROCESS_MODULE = subprocess.__name__


def render_status(name: str) -> str:
    subprocess.run(["python", "--version"], check=False)  # noqa: S603,S607
    return f"ready:{name}:{_SUBPROCESS_MODULE}"
