from abc import ABC, abstractmethod
from .connection_types import Connection
from .dialetecs import SQLDialect
from typing import List, Optional, Dict, Tuple, Any

class BaseQuery(ABC):
    """
    Abstract base class for query builders.
    Defines the interface for concrete query classes.
    """
    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name
        self.client: Connection = getattr(self.__class__, 'connection', None)
        self.dialect: SQLDialect = getattr(self.__class__, 'dialect', None)
        if self.client is None or self.dialect is None:
            raise RuntimeError("Connection or dialect not set. Use set_connection first.")

    @classmethod
    def set_connection(cls, connection: Connection):
        """Sets the connection to be used by the model."""
        cls.connection = connection
        cls.dialect = connection.dialect  # Set dialect from connection

    @abstractmethod
    def to_sql(self) -> Tuple[str, Optional[tuple]]:
        """Abstract method to convert the query to SQL and parameters."""
        pass

    def run(self) -> List[Dict[str, Any]]:
        """Executes the query using the provided connection."""
        sql, params = self.to_sql()
        return self.client.run(sql, params)