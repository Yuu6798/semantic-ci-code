from collections.abc import Callable


class Auth:
    def login_required(self, fn: Callable) -> Callable:
        return fn


auth = Auth()


@auth.login_required
def account_dashboard(user_id: str) -> str:
    return f"dashboard:{user_id}"
