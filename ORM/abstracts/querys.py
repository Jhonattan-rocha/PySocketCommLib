from abc import ABC, abstractmethod
from .connection_types import Connection
from .dialetecs import SQLDialect
from typing import List, Optional, Dict, Tuple, Any

class BaseQuery(ABC):
    """
    Abstract base class for query builders.
    Defines the interface for concrete query classes.
    """
    def __init__(self, client: Connection, dialect: SQLDialect, table_name: Optional[str] = None):
        self.client = client
        self.dialect = dialect
        self._table_name = table_name

    @abstractmethod
    def to_sql(self) -> Tuple[str, Optional[tuple]]:
        """Abstract method to convert the query to SQL and parameters."""
        pass

    def run(self) -> List[Dict[str, Any]]:
        """Executes the query using the provided connection."""
        sql, params = self.to_sql()
        return self.client.run(sql, params)