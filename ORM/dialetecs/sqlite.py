from ..abstracts.dialetecs import SQLDialect
from ..abstracts.field_types import BaseField
from ..abstracts.connection_types import Connection
from ...exceptions import ConnectionError as OrmConnectionError
import sqlite3
from typing import List, Dict, Any, Tuple, Optional

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
            raise OrmConnectionError("Database connection not established. Call connect() first.")
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

    def begin(self) -> None:
        if self._conn:
            self._conn.isolation_level = 'DEFERRED'

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn:
            self._conn.rollback()

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
            "INTEGER":    "INTEGER",
            "SMALLINT":   "INTEGER",
            "BIGINT":     "INTEGER",
            "AUTOFIELD":  "INTEGER",   # INTEGER PRIMARY KEY é auto-increment no SQLite
            "TEXT":       "TEXT",
            "REAL":       "REAL",
            "DECIMAL":    "REAL",
            "BOOLEAN":    "INTEGER",   # SQLite não tem BOOLEAN nativo
            "TIMESTAMP":  "TEXT",      # SQLite não tem DATETIME nativo
            "JSONB":      "TEXT",
            "UUID":       "TEXT",
            "BINARY":     "BLOB",
        }
        return mapping.get(field.get_sql_type(), field.get_sql_type())

    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        if primary_keys:
            quoted = [self.quote_identifier(k) for k in primary_keys]
            return f", PRIMARY KEY ({', '.join(quoted)})"
        return ""

    def quote_identifier(self, identifier: str) -> str:
        if '.' in identifier:
            table, col = identifier.split('.', 1)
            return f'"{table}"."{col}"'
        return f'"{identifier}"'

    def placeholder(self, data_len: int) -> List[str]:
        return ['?'] * data_len

    def parser(self, result):
        # SqliteConnection.run() already returns list[dict]
        return result if result else []

    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        columns = ', '.join(self.quote_identifier(k) for k in data.keys())
        placeholders = ', '.join(['?'] * len(data))
        return f"INSERT INTO {quoted_table} ({columns}) VALUES ({placeholders})", tuple(data.values())

    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        set_clause = ', '.join(f"{self.quote_identifier(k)} = ?" for k in data.keys())
        return f"UPDATE {quoted_table} SET {set_clause} WHERE {where_condition}", tuple(data.values())

    def delete(self, table_name: str, where_condition: str) -> str:
        return f"DELETE FROM {self.quote_identifier(table_name)} WHERE {where_condition}"

    def select(
        self,
        table_name: str,
        columns: List[str],
        where_condition: Optional[str] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        joins: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        select_cols = (
            ', '.join(self.quote_identifier(c) if c != '*' else '*' for c in columns)
            if columns else '*'
        )
        sql = f"SELECT {select_cols} FROM {quoted_table}"

        if joins:
            for j in joins:
                join_table = self.quote_identifier(j['table'])
                join_type = j.get('type', 'INNER').upper()
                sql += f" {join_type} JOIN {join_table} ON {j['condition']}"

        if where_condition:
            sql += f" WHERE {where_condition}"

        if order_by:
            sql += f" ORDER BY {', '.join(self._quote_order_item(c) for c in order_by)}"

        if limit is not None:
            sql += f" LIMIT {limit}"

        if offset is not None:
            sql += f" OFFSET {offset}"

        return sql, ()


    def upsert(
        self,
        table_name: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        """SQLite 3.24+: INSERT … ON CONFLICT (cols) DO UPDATE SET …"""
        quoted_table = self.quote_identifier(table_name)
        cols = list(data.keys())
        quoted_cols = ', '.join(self.quote_identifier(c) for c in cols)
        placeholders = ', '.join(['?'] * len(cols))

        to_update = update_columns or [c for c in cols if c not in conflict_columns]
        conflict_targets = ', '.join(self.quote_identifier(c) for c in conflict_columns)
        set_clause = ', '.join(
            f"{self.quote_identifier(c)} = excluded.{self.quote_identifier(c)}"
            for c in to_update
        )

        sql = (
            f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({placeholders})\n"
            f"ON CONFLICT ({conflict_targets}) DO UPDATE SET {set_clause}"
        )
        return sql, tuple(data.values())
