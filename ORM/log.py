"""
Logging configuration helpers for PySocketCommLib ORM.

By default the ORM uses Python's standard ``logging`` module with a
``NullHandler`` so no output is produced unless the calling application
configures logging.  This is the recommended practice for library code
(see https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library).

Usage in application code::

    import logging

    # Show all ORM debug messages (queries, connections, migrations …)
    logging.getLogger("PySocketCommLib.ORM").setLevel(logging.DEBUG)

    # Or configure a handler to write to a file:
    handler = logging.FileHandler("orm.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logging.getLogger("PySocketCommLib.ORM").addHandler(handler)

    # Or use the convenience helper shipped with this module:
    from PySocketCommLib.ORM.log import setup_logging
    setup_logging(level=logging.DEBUG)
"""

import logging
import sys
from typing import Optional


# Attach a NullHandler to the root ORM logger so that libraries using
# PySocketCommLib do not get "No handlers could be found" warnings.
logging.getLogger("PySocketCommLib").addHandler(logging.NullHandler())


def setup_logging(
    level: int = logging.INFO,
    handler: Optional[logging.Handler] = None,
    fmt: str = "%(asctime)s %(name)s %(levelname)s %(message)s",
) -> None:
    """
    Convenience helper to quickly enable ORM logging.

    Attaches a ``StreamHandler`` (stdout) to the ``PySocketCommLib`` root
    logger if no other handler is provided.

    Args:
        level:   Log level for the ``PySocketCommLib`` logger (default INFO).
        handler: Custom handler to attach. Defaults to ``StreamHandler(stdout)``.
        fmt:     Log format string.

    Example::

        from PySocketCommLib.ORM.log import setup_logging
        import logging

        setup_logging(level=logging.DEBUG)   # shows all queries & connections
    """
    root_logger = logging.getLogger("PySocketCommLib")

    if handler is None:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
