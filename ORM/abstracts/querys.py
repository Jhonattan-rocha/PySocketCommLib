from abc import ABC, abstractmethod
from .connection_types import Connection
from .dialetecs import SQLDialect

class BaseQuery(ABC):
    """
    Abstract base class for query builders.
    Defines the interface for concrete query classes.
    """
    def __init__(self, client: Connection, dialect: SQLDialect, table_name: str = None):
        self.client = client
        self.dialect = dialect
        self._table_name = table_name

    @abstractmethod
    def to_sql(self) -> str:
        """Abstract method to convert the query to SQL."""
        pass

    def run(self):
        """Executes the query using the provided connection."""
        sql = self.to_sql()
        return self.client.run(sql)