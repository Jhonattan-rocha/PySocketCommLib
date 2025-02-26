from abc import ABC, abstractmethod
from .querys import BaseQuery

class Connection(ABC):
    """
    Abstract base class for database connections.
    Defines the interface for concrete connection classes.
    """
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._conn = None 
        self.dialect = None

    @abstractmethod
    def connect(self):
        """Abstract method to establish a database connection."""
        pass

    @abstractmethod
    def disconnect(self):
        """Abstract method to close the database connection."""
        pass

    @abstractmethod
    def run(self, sql: str, params: tuple = None):
        """Abstract method to execute a SQL query."""
        pass
