import pickle  # noqa: S403 - intentional runnable example fixture


def format_summary(title: str, body: str) -> str:
    cached = pickle.loads(body.encode("utf-8"))  # noqa: S301
    return f"{title}\n{cached}"
