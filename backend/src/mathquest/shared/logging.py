"""Process-wide logging setup."""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Send log records to stderr at the given level; safe to call more than once."""
    logging.basicConfig(level=level.upper(), format=_FORMAT, stream=sys.stderr, force=True)
