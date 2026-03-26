from abc import ABC, abstractmethod
from .field_types import BaseField
from typing import Dict, Any, List, Tuple, Optional

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

    @abstractmethod
    def select(self, table_name: str, columns: List[str], where_condition: Optional[str] = None, order_by: Optional[List[str]] = None, limit: Optional[int] = None, offset: Optional[int] = None, joins: Optional[List[Dict[str, str]]] = None) -> Tuple[str, tuple]:
        """Abstract method to generate SELECT SQL and parameters."""
        pass

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Abstract method to properly quote identifiers (table and column names) for the dialect."""
        pass

    @abstractmethod
    def placeholder(self, data_len: int) -> list[str]:
        """Abstract method to get the placeholder for parameterized queries."""
        pass

    @abstractmethod
    def parser(self, result: tuple):
        """Abstract method to serialize results."""
        pass

    def _quote_order_item(self, item: str) -> str:
        """
        Quote the column name in an ORDER BY expression, preserving ASC/DESC.

        Examples:
            "name"       → '"name"'   (double-quoted for psql)
            "name DESC"  → '"name" DESC'
            "name ASC"   → '"name" ASC'
        """
        parts = item.rsplit(' ', 1)
        if len(parts) == 2 and parts[1].upper() in ('ASC', 'DESC'):
            return f"{self.quote_identifier(parts[0])} {parts[1].upper()}"
        return self.quote_identifier(item)

    @abstractmethod
    def upsert(
        self,
        table_name: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        """
        Generate an INSERT … ON CONFLICT … DO UPDATE (upsert) statement.

        Args:
            table_name:        Target table.
            data:              Column → value mapping for the INSERT.
            conflict_columns:  Columns that define uniqueness (PK or unique index).
            update_columns:    Columns to overwrite on conflict.
                               Defaults to all columns that are NOT in conflict_columns.

        Returns:
            (sql, params) ready for connection.run().
        """
        pass