"""Yii-style flash message helpers backed by SessionMiddleware.

Mirrors the Yii \\common\\widgets\\Alert pattern: handlers call flash()
before redirecting; the next page renders + clears the queue exactly once.

Storage shape: request.session["_flashes"] = [[category, message], ...]
"""

from typing import Iterable, List, Tuple


_KEY = "_flashes"


def flash(request, category: str, message: str) -> None:
    """Append a flash to the user's session.

    No-op (with a debug log to stderr) if SessionMiddleware is not
    installed — keeps tests/legacy callers from blowing up on a missing
    request.session attribute.
    """
    try:
        session = request.session
    except (AssertionError, AttributeError):
        # AssertionError: starlette raises when SessionMiddleware missing.
        return
    bucket = session.get(_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append([str(category), str(message)])
    session[_KEY] = bucket


def get_flashes(request) -> List[Tuple[str, str]]:
    """Pop all flashes for this request, returning [(category, message), ...]."""
    try:
        session = request.session
    except (AssertionError, AttributeError):
        return []
    raw = session.pop(_KEY, None)
    if not raw:
        return []
    out: List[Tuple[str, str]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((str(item[0]), str(item[1])))
    return out


def has_flashes(request) -> bool:
    try:
        return bool(request.session.get(_KEY))
    except (AssertionError, AttributeError):
        return False


__all__: Iterable[str] = ("flash", "get_flashes", "has_flashes")
