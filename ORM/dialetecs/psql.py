from ..abstracts.dialetecs import SQLDialect
from ..abstracts.connection_types import Connection
from ..abstracts.querys import BaseQuery
from ..drivers.psql import PostgreSQLSocketClient
from ..abstracts.field_types import BaseField
from typing import Any, Dict, List, Tuple

class PsqlConnection(Connection):
    def connect(self):
        db = PostgreSQLSocketClient(host=self.host, port=self.port, username=self.user, password=self.password, database_name=self.database)
        if db.connect():
            self.__conn = db
        else:
            raise ConnectionError("Invalid user name, password or database name not exists")

    def disconnect(self):
        self.__conn.disconnect()
    
    def run(self, query: BaseQuery):
        self.__conn.run(query.to_sql())

class PostgreSQLDialect(SQLDialect):
    """Generates SQL for PostgreSQL databases."""
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
                column_definition += f" DEFAULT '{field.default}'" # PostgreSQL uses single quotes for default values
            column_definitions.append(column_definition)

        primary_key_constraint = self.get_primary_key_constraint(primary_keys)
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)}{primary_key_constraint})"

    def get_sql_type(self, field: BaseField) -> str:
        mapping = {
            "INTEGER": "SERIAL" if field.primary_key else "INTEGER",
            "TEXT": "TEXT",
            "REAL": "REAL",
            "BOOLEAN": "BOOLEAN",
            "TIMESTAMP": "TIMESTAMP"
        }
        return mapping.get(field.get_sql_type(), field.get_sql_type())

    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        if primary_keys:
            return f", PRIMARY KEY ({', '.join(primary_keys)})"
        return ""

    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))  # PostgreSQL uses %s as placeholder
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        params = tuple(data.values())
        return sql, params

    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])  # PostgreSQL uses %s as placeholder
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_condition}"
        params = tuple(data.values())
        return sql, params

    def delete(self, table_name: str, where_condition: str) -> str:
        return f"DELETE FROM {table_name} WHERE {where_condition}"