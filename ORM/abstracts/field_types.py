from abc import ABC, abstractmethod

class BaseField(ABC):
    """
    Abstract base class for defining database fields.
    Provides a common interface for different field types.
    """
    def __init__(self, db_column_name: str = None, primary_key=False, nullable=True, unique=False, default=None):
        self.db_column_name = db_column_name
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique
        self.default = default

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