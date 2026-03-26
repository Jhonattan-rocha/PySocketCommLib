from abc import ABC, abstractmethod
from contextlib import contextmanager
from ..abstracts.dialetecs import SQLDialect
from typing import Optional, Any, Generator


class Connection(ABC):
    """
    Abstract base class for database connections.
    Defines the interface for concrete connection classes.
    """
    def __init__(self, host: Optional[str], port: Optional[int], user: Optional[str], password: Optional[str], database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._conn = None
        self.dialect: SQLDialect = None
        self._prepared_statement_cache = {}

    @abstractmethod
    def connect(self) -> bool:
        """Abstract method to establish a database connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Abstract method to close the database connection."""
        pass

    @abstractmethod
    def run(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Abstract method to execute a SQL query."""
        pass

    # ------------------------------------------------------------------
    # Transaction control — subclasses override to use native API.
    # Default implementations use raw SQL so every driver works out-of-the-box.
    # ------------------------------------------------------------------

    def begin(self) -> None:
        """Start an explicit transaction."""
        self.run("BEGIN")

    def commit(self) -> None:
        """Commit the current transaction."""
        self.run("COMMIT")

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self.run("ROLLBACK")

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """
        Context manager for atomic database operations.

        Usage::

            with connection.transaction():
                connection.run("INSERT INTO ...")
                connection.run("UPDATE ...")
            # auto-commit on success, auto-rollback on exception
        """
        self.begin()
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise

    @property
    def connection(self):
        return self._conn