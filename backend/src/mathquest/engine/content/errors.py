"""The one error type for malformed or inconsistent content."""


class ContentError(Exception):
    """A content pack is malformed or internally inconsistent.

    The message starts with the pack-relative file and the path inside it, for example
    ``lessons/add_within_20.yaml: screens[1].visual.kind: ...``.
    """
