from collections.abc import Callable


def login_required(fn: Callable) -> Callable:
    return fn


@login_required
def account_dashboard(user_id: str) -> str:
    return f"dashboard:{user_id}"
