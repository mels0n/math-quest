"""Path normalisation shared by the admin gate and the static handler.

Both must treat a path the same way, or the difference between them reveals which paths exist.
A path is checked as sent, decoded once and decoded twice, with case folded, empty and `.`
segments dropped and `..` resolved.
"""

from collections.abc import Sequence
from urllib.parse import unquote

from starlette.types import Scope


def segments(path: str) -> list[str]:
    parts: list[str] = []
    for seg in path.replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg.casefold())
    return parts


def _forms(path: str) -> tuple[str, str, str]:
    once = unquote(path)
    return path, once, unquote(once)


def path_is_under(path: str, prefix: Sequence[str]) -> bool:
    """Whether any decoding of `path` normalises to something at or below `prefix`."""
    return any(segments(form)[: len(prefix)] == list(prefix) for form in _forms(path))


def scope_is_under(scope: Scope, prefix: Sequence[str]) -> bool:
    """`path_is_under` over both the decoded path and the raw path of an ASGI scope."""
    candidates = [scope.get("path", "")]
    raw = scope.get("raw_path")
    if isinstance(raw, bytes):
        candidates.append(raw.decode("latin-1").split("?", 1)[0])
    return any(path_is_under(candidate, prefix) for candidate in candidates)
