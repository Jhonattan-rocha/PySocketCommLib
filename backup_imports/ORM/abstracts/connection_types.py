from abc import ABC, abstractmethod
from ..abstracts.dialetecs import SQLDialect
from typing import Optional, Any

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

    @property
    def connection(self):
        return self._conn