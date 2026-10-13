"""Typed domain errors. The API layer maps these to HTTP in one place."""


class DomainError(Exception):
    """Base class for every expected, user-facing failure."""


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Unauthorized(DomainError):
    pass


class Locked(DomainError):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"locked for {retry_after_s}s")
        self.retry_after_s = retry_after_s


class Invalid(DomainError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
