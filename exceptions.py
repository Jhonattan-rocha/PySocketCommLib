"""
Custom exception hierarchy for PySocketCommLib.

Import from the package root:
    from PySocketCommLib.exceptions import ValidationError, MissingWhereClauseError
"""


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

class PySocketCommError(Exception):
    """Base exception for all PySocketCommLib errors."""


# ---------------------------------------------------------------------------
# ORM
# ---------------------------------------------------------------------------

class ORMError(PySocketCommError):
    """Base for all ORM-related errors."""


class ConnectionError(ORMError):
    """
    Raised when a database connection cannot be established or is lost.

    Examples:
        - Host unreachable
        - Authentication failure at the DB level
        - Connection used after being closed
    """


class QueryError(ORMError):
    """Raised when a query cannot be built or executed correctly."""


class MissingWhereClauseError(QueryError):
    """
    Raised when an UPDATE or DELETE is attempted without a WHERE clause
    and ``force=True`` was not passed.
    """


class ValidationError(ORMError):
    """
    Raised when a model field value fails validation.

    Attributes:
        field_name: Name of the field that failed validation (if known).
    """

    def __init__(self, message: str, field_name: str = ""):
        super().__init__(message)
        self.field_name = field_name


class MigrationError(ORMError):
    """Base for migration-related errors."""


class UnmetDependencyError(MigrationError):
    """
    Raised when a migration depends on another that has not been applied yet.

    Attributes:
        migration: Name of the migration being applied.
        dependency: Name of the missing dependency.
    """

    def __init__(self, migration: str, dependency: str):
        super().__init__(
            f"Migration '{migration}' depends on '{dependency}' "
            f"which has not been applied yet."
        )
        self.migration = migration
        self.dependency = dependency


class CircularDependencyError(MigrationError):
    """
    Raised when a circular or unresolvable dependency is detected
    among a set of migrations.

    Attributes:
        migrations: Names of the migrations involved in the cycle.
    """

    def __init__(self, migrations: list):
        super().__init__(
            f"Circular or unresolvable dependency among migrations: {migrations}"
        )
        self.migrations = migrations


# ---------------------------------------------------------------------------
# Network / Transport
# ---------------------------------------------------------------------------

class NetworkError(PySocketCommError):
    """Base for network and transport errors."""


class AuthError(NetworkError):
    """Raised when authentication fails (wrong token, missing credentials, etc.)."""


class EncryptionError(NetworkError):
    """Raised when encryption or decryption fails."""


class ProtocolError(NetworkError):
    """Raised when a protocol-level violation is detected (bad handshake, frame, etc.)."""
