from abc import ABC, abstractmethod

class BaseField(ABC):
    def __init__(self, db_column_name: str = None, primary_key=False, nullable=True, unique=False):
        self.db_column_name = db_column_name
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique

    @abstractmethod
    def get_sql_type(self):
        pass

class IntegerField(BaseField):
    def get_sql_type(self):
        return "INTEGER"

class TextField(BaseField):
    def get_sql_type(self):
        return "TEXT"

class FloatField(BaseField):
    def get_sql_type(self):
        return "REAL"

class BooleanField(BaseField):
    def get_sql_type(self):
        return "BOOLEAN"

class DateTimeField(BaseField):
    def get_sql_type(self):
        return "TIMESTAMP"