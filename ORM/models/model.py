from ..abstracts.field_types import BaseField
from ..abstracts.dialetecs import SQLDialect 
from ..abstracts.connection_types import Connection
from typing import Tuple, Dict, List, Any, Optional

class BaseModel:
    """
    Base class for database models.
    Provides ORM-like functionality for interacting with databases.
    """
    dialect: SQLDialect = None  # Dialect to be set by concrete models
    connection: Connection = None  # Connection instance to be set

    @classmethod
    def set_connection(cls, connection: Connection):
        """Sets the connection to be used by the model."""
        cls.connection = connection
        cls.dialect = connection.dialect  # Set dialect from connection

    @classmethod
    def get_table_name(cls):
        """Converts class name to snake_case for table name."""
        name = cls.__name__
        return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

    @classmethod
    def get_fields(cls) -> Tuple[Dict[str, 'BaseField'], List[str]]:
        """Returns a dictionary of fields defined in the model and a list of primary key column names."""
        fields = {}
        primary_keys = []
        for name, field in cls.__dict__.items():
            if isinstance(field, BaseField):
                fields[name] = field
                db_column_name = field.db_column_name if field.db_column_name else name
                if field.primary_key:
                    primary_keys.append(db_column_name)
        return fields, primary_keys

    @classmethod
    def create_table_sql(cls) -> str:
        """Generates CREATE TABLE SQL based on model fields and dialect."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")

        table_name = cls.get_table_name()
        fields, primary_keys = cls.get_fields()
        return cls.dialect.create_table(table_name, fields, primary_keys)

    @classmethod
    def create_table(cls):
        """Creates the table in the database."""
        if not cls.connection:
            raise Exception("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql = cls.create_table_sql()
        cls.connection.run(sql)

    def __init__(self, **kwargs):
        """Initializes a model instance with provided keyword arguments."""
        fields, _ = self.__class__.get_fields()
        for name, field in fields.items():
            db_column_name = field.db_column_name if field.db_column_name else name
            if name in kwargs:
                setattr(self, name, kwargs[name])
            elif db_column_name in kwargs:
                setattr(self, name, kwargs[db_column_name])
            else:
                setattr(self, name, field.default) # Set to field's default if provided, else remains None (default behavior of setattr if not set explicitly)

        self._data = {}  # To track data for insert/update (not fully implemented here)

    @classmethod
    def insert_sql(cls, data: Dict[str, Any]) -> Tuple[str, tuple]:
        """Generates INSERT SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.insert(table_name, data)

    def save(self):
        """Saves (inserts or updates) the model instance to the database."""
        if not self.__class__.connection:
            raise Exception("No database connection set. Call set_connection() on the BaseModel subclass.")

        table_name = self.__class__.get_table_name()
        fields, primary_keys = self.__class__.get_fields()
        data_to_insert = {}
        for name, field in fields.items():
            db_column_name = field.db_column_name if field.db_column_name else name
            data_to_insert[db_column_name] = getattr(self, name)

        sql, params = self.__class__.insert_sql(data_to_insert)
        
        self.__class__.connection.run(sql, params)

    @classmethod
    def delete_sql(cls, where_condition: str) -> str:
        """Generates DELETE SQL for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.delete(table_name, where_condition)

    @classmethod
    def delete(cls, where_condition: str):
        """Deletes records based on a WHERE condition."""
        if not cls.connection:
            raise Exception("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql = cls.delete_sql(where_condition)
        cls.connection.run(sql)

    @classmethod
    def update_sql(cls, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        """Generates UPDATE SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.update(table_name, data, where_condition)

    @classmethod
    def update(cls, data: Dict[str, Any], where_condition: str):
        """Updates records based on a WHERE condition."""
        if not cls.connection:
            raise Exception("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql, params = cls.update_sql(data, where_condition)
        cls.connection.run(sql, params)

    @classmethod
    def select_sql(cls, columns: List[str] = None, where_condition: Optional[str] = None, order_by: Optional[List[str]] = None, limit: Optional[int] = None, joins: Optional[List[Dict[str, str]]] = None) -> Tuple[str, tuple]:
        """Generates SELECT SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        columns_to_select = columns if columns else ["*"] # Select all if no columns specified
        return cls.dialect.select(table_name, columns_to_select, where_condition, order_by, limit, joins)

    @classmethod
    def select(cls, columns: List[str] = None, where_condition: Optional[str] = None, order_by: Optional[List[str]] = None, limit: Optional[int] = None, joins: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """Selects records based on various conditions."""
        if not cls.connection:
            raise Exception("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql, params = cls.select_sql(columns, where_condition, order_by, limit, joins)
        return cls.connection.run(sql, params)
