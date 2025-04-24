from ..abstracts.dialetecs import SQLDialect
from ..abstracts.field_types import BaseField
from ..abstracts.connection_types import Connection
import sqlite3
from typing import List, Dict, Any, Tuple

class SqliteConnection(Connection):
    """Concrete Connection class for SQLite, using sqlite3 module."""
    def __init__(self, database: str): # SQLite only needs database file path
        super().__init__(host=None, port=None, user=None, password=None, database=database) # Host, port, user, password are not relevant for SQLite
        self.dialect = SqliteDialect() # Assign the SQLite dialect

    def connect(self):
        """Connects to the SQLite database using sqlite3."""
        try:
            print(f"Connecting to SQLite database: {self.database}")
            self._conn = sqlite3.connect(self.database) # Establishes connection using sqlite3
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to SQLite database: {e}")
            return False

    def disconnect(self):
        """Disconnects from the SQLite database."""
        if self._conn:
            try:
                self._conn.close()
                print("Disconnecting from SQLite")
            except sqlite3.Error as e:
                print(f"Error disconnecting from SQLite database: {e}")
            finally:
                self._conn = None

    def run(self, sql: str, params: tuple = None):
        """Executes SQL queries on the SQLite database using sqlite3."""
        if not self._conn:
            raise Exception("Database connection not established. Call connect() first.")
        cursor = self._conn.cursor()
        try:
            if params:
                cursor.execute(sql, params) # Execute with parameters to prevent SQL injection
            else:
                cursor.execute(sql)
            if sql.lstrip().upper().startswith("SELECT"): # Handle SELECT queries and return results
                results = cursor.fetchall()
                column_names = [description[0] for description in cursor.description] # Get column names
                return [dict(zip(column_names, row)) for row in results] # Return list of dictionaries
            else:
                self._conn.commit() # Commit changes for INSERT, UPDATE, DELETE
                return True # Indicate successful execution for non-SELECT queries
        except sqlite3.Error as e:
            self._conn.rollback() # Rollback in case of error to maintain data integrity
            print(f"Error executing SQL on SQLite: {e}\nSQL: {sql}\nParams: {params}")
            raise # Re-raise the exception for the caller to handle

    @property
    def connection(self):
        return self._conn

class SqliteDialect(SQLDialect):
    """Generates SQL for SQLite databases."""
    def create_table(self, table_name: str, columns: Dict[str, 'BaseField'], primary_keys: List[str]) -> str:
        column_definitions = []
        for name, field in columns.items():
            db_column_name = field.db_column_name if field.db_column_name else name
            sql_type = self.get_sql_type(field)
            column_definition = f"{db_column_name} {sql_type}"
            if not field.nullable:
                column_definition += " NOT NULL"
            if field.unique:
                column_definition += " UNIQUE"
            if field.default is not None: # Added default value handling
                column_definition += f" DEFAULT '{field.default}'" # SQLite uses single quotes for default values
            column_definitions.append(column_definition)

        primary_key_constraint = self.get_primary_key_constraint(primary_keys)
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)}{primary_key_constraint})"

    def get_sql_type(self, field: BaseField) -> str:
        mapping = {
            "INTEGER": "INTEGER",
            "TEXT": "TEXT",
            "REAL": "REAL",
            "BOOLEAN": "INTEGER", # SQLite uses INTEGER to store boolean
            "TIMESTAMP": "TEXT" # SQLite doesn't have native DATETIME, using TEXT for simplicity
        }
        return mapping.get(field.get_sql_type(), field.get_sql_type())

    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        if primary_keys:
            return f", PRIMARY KEY ({', '.join(primary_keys)})"
        return ""

    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))  # SQLite uses ? as placeholder
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        params = tuple(data.values())
        return sql, params

    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])  # SQLite uses ? as placeholder
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_condition}"
        params = tuple(data.values())
        return sql, params

    def delete(self, table_name: str, where_condition: str) -> str:
        return f"DELETE FROM {table_name} WHERE {where_condition}"
