from abc import ABC, abstractmethod
from .field_types import BaseField
from typing import Dict, Any, List, Tuple

class SQLDialect(ABC):
    """
    Abstract base class for SQL dialects.
    Provides dialect-specific SQL syntax.
    """
    @abstractmethod
    def create_table(self, table_name: str, columns: Dict[str, 'BaseField'], primary_keys: List[str]) -> str:
        """Abstract method to generate CREATE TABLE SQL."""
        pass

    @abstractmethod
    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        """Abstract method to define primary key constraint syntax."""
        pass

    @abstractmethod
    def get_sql_type(self, field: 'BaseField') -> str:
        """Abstract method to get SQL type for a field."""
        pass

    @abstractmethod
    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        """Abstract method to generate INSERT SQL and parameters."""
        pass

    @abstractmethod
    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        """Abstract method to generate UPDATE SQL and parameters."""
        pass

    @abstractmethod
    def delete(self, table_name: str, where_condition: str) -> str:
        """Abstract method to generate DELETE SQL."""
        pass