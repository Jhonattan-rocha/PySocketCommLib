from abc import ABC, abstractmethod
from typing import Optional

class BaseField(ABC):
    """
    Abstract base class for defining database fields.
    Provides a common interface for different field types.
    """
    def __init__(self, db_column_name: Optional[str] = None, primary_key=False, nullable=True, unique=False, default=None, index=False): # Added index
        self.db_column_name = db_column_name
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique
        self.default = default
        self.index = index # Added index property

    @abstractmethod
    def get_sql_type(self) -> str:
        """Abstract method to get the SQL type of the field."""
        pass
class IntegerField(BaseField):
    def get_sql_type(self) -> str:
        return "INTEGER"


class TextField(BaseField):
    def get_sql_type(self) -> str:
        return "TEXT"


class FloatField(BaseField):
    def get_sql_type(self) -> str:
        return "REAL"


class BooleanField(BaseField):
    def get_sql_type(self) -> str:
        return "BOOLEAN"


class DateTimeField(BaseField):
    def get_sql_type(self) -> str:
        return "TIMESTAMP"

class JSONField(BaseField): 
    def get_sql_type(self) -> str:
        return "JSONB" 

class UUIDField(BaseField):
    def get_sql_type(self) -> str:
        return "UUID"

class DecimalField(BaseField):
    def get_sql_type(self) -> str:
        return "DECIMAL"

class ForeignKeyField(BaseField):
    def __init__(
        self,
        reference_table: str,
        reference_column: str = "id",
        on_delete: str = "CASCADE",
        on_update: str = "CASCADE",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.reference_table = reference_table
        self.reference_column = reference_column
        self.on_delete = on_delete
        self.on_update = on_update

    def get_sql_type(self) -> str:
        return "INTEGER"

    def get_foreign_key_clause(self, column_name: str) -> str:
        return (
            f'FOREIGN KEY ("{column_name}") '
            f'REFERENCES "{self.reference_table}"("{self.reference_column}") '
            f'ON DELETE {self.on_delete} ON UPDATE {self.on_update}'
        )
