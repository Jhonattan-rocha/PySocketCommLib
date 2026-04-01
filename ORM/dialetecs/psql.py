import logging
import uuid
from typing import Any, Dict, List, Tuple, Optional

from ..abstracts.dialetecs import SQLDialect
from ..abstracts.connection_types import Connection
from ..drivers.psql import PostgreSQLSocketClient
from ..abstracts.field_types import BaseField, ForeignKeyField
from ...exceptions import ConnectionError as OrmConnectionError

logger = logging.getLogger(__name__)

class PsqlConnection(Connection):
    def connect(self):
        try:
            db = PostgreSQLSocketClient(host=self.host, port=self.port, username=self.user, password=self.password, database_name=self.database)
            if db.connect():
                self._conn = db
                self.dialect = PostgreSQLDialect() # Initialize dialect here!
                return True
            else:
                return False # Connect method in mock client already returns bool, consistent return
        except Exception as e:
            logger.error("PostgreSQL connection failed: %s", e)
            return False


    def disconnect(self):
        if self._conn:
            self._conn.disconnect()
            self._conn = None

    def run(self, sql: str, params: Optional[tuple] = None) -> Any:
        if not self._conn:
            raise OrmConnectionError("Database connection is not established. Call connect() first.")
        query_signature = sql
        new_statement_name = uuid.uuid4().__str__()
        prepared_statement_name = self._prepared_statement_cache.get(query_signature)
        
        if not params:
            return self._conn.run(sql)
        
        if prepared_statement_name:
            return self._conn.execute_prepared_statement(prepared_statement_name, [str(param) for param in params])
        else:
            self._conn.prepare_statement(new_statement_name, sql, None)
            self._prepared_statement_cache[query_signature] = new_statement_name
            return self._conn.execute_prepared_statement(new_statement_name, [str(param) for param in params])

    def begin(self) -> None:
        if self._conn:
            self._conn.begin()

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn:
            self._conn.rollback()

class PostgreSQLDialect(SQLDialect):
    """Generates SQL for PostgreSQL databases."""
    def create_table(self, table_name: str, columns: Dict[str, 'BaseField'], primary_keys: List[str]) -> str:
        quoted_table_name = self.quote_identifier(table_name)
        column_definitions = []
        for name, field in columns.items():
            db_column_name = self.quote_identifier(field.db_column_name if field.db_column_name else name)
            sql_type = self.get_sql_type(field)
            column_definition = f"{db_column_name} {sql_type}"
            if not field.nullable:
                column_definition += " NOT NULL"
            if field.unique:
                column_definition += " UNIQUE"
            if field.default is not None: # Added default value handling
                column_definition += f" DEFAULT '{field.default}'" # PostgreSQL uses single quotes for default values
            if field.index: # Add index creation within table definition
                column_definition += " INDEX" # While not direct syntax, we handle index creation separately for clarity or can use constraint based index
            column_definitions.append(column_definition)

        primary_key_constraint = self.get_primary_key_constraint(primary_keys)
        foreign_keys = []

        for name, field in columns.items():
            if isinstance(field, ForeignKeyField):
                db_column_name = field.db_column_name if field.db_column_name else name
                fk_clause = field.get_foreign_key_clause(db_column_name)
                foreign_keys.append(fk_clause)

        # Junte os FKs com o resto da definição
        full_definitions = column_definitions
        if foreign_keys:
            full_definitions.extend(foreign_keys)

        return f"CREATE TABLE IF NOT EXISTS {quoted_table_name} ({', '.join(full_definitions)}{primary_key_constraint})"


    def get_sql_type(self, field: BaseField) -> str:
        sql_type = field.get_sql_type()
        mapping = {
            "INTEGER":   "SERIAL" if field.primary_key else "INTEGER",
            "SMALLINT":  "SMALLINT",
            "BIGINT":    "BIGINT",
            "AUTOFIELD": "SERIAL",
            "TEXT":      "TEXT",
            "REAL":      "REAL",
            "DECIMAL":   "DECIMAL",
            "BOOLEAN":   "BOOLEAN",
            "TIMESTAMP": "TIMESTAMP",
            "JSONB":     "JSONB",
            "UUID":      "UUID",
            "BINARY":    "BYTEA",
        }
        return mapping.get(sql_type, sql_type)

    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        if primary_keys:
            quoted_keys = [self.quote_identifier(key) for key in primary_keys]
            return f", PRIMARY KEY ({', '.join(quoted_keys)})"
        return ""

    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        quoted_table_name = self.quote_identifier(table_name)
        columns = ', '.join([self.quote_identifier(col) for col in data.keys()]) # Quote column names
        placeholders = ', '.join(self.placeholder(len(data))) # Use dialect placeholder
        sql = f"INSERT INTO {quoted_table_name} ({columns}) VALUES ({placeholders})"
        params = tuple(data.values())
        return sql, params

    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        quoted_table_name = self.quote_identifier(table_name)
        set_clause = ', '.join([f"{self.quote_identifier(key)} = {placeholder}" for key, placeholder in zip(data.keys(), self.placeholder(len(data)))]) # Quote column names, use placeholder
        sql = f"UPDATE {quoted_table_name} SET {set_clause} WHERE {where_condition}"
        params = tuple(data.values())
        return sql, params

    def delete(self, table_name: str, where_condition: str) -> str:
        quoted_table_name = self.quote_identifier(table_name)
        return f"DELETE FROM {quoted_table_name} WHERE {where_condition}"

    def upsert(
        self,
        table_name: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        """PostgreSQL: INSERT … ON CONFLICT (cols) DO UPDATE SET … EXCLUDED …"""
        quoted_table = self.quote_identifier(table_name)
        cols = list(data.keys())
        quoted_cols = ', '.join(self.quote_identifier(c) for c in cols)
        placeholders = ', '.join(self.placeholder(len(cols)))

        to_update = update_columns or [c for c in cols if c not in conflict_columns]
        conflict_targets = ', '.join(self.quote_identifier(c) for c in conflict_columns)
        set_clause = ', '.join(
            f"{self.quote_identifier(c)} = EXCLUDED.{self.quote_identifier(c)}"
            for c in to_update
        )

        sql = (
            f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({placeholders})\n"
            f"ON CONFLICT ({conflict_targets}) DO UPDATE SET {set_clause}"
        )
        return sql, tuple(data.values())

    def select(self, table_name: str, columns: List[str], where_condition: Optional[str] = None, order_by: Optional[List[str]] = None, limit: Optional[int] = None, offset: Optional[int] = None, joins: Optional[List[Dict[str, str]]] = None) -> Tuple[str, tuple]:
        quoted_table_name = self.quote_identifier(table_name)
        select_columns = (
            ', '.join(self.quote_identifier(c) if c != '*' else '*' for c in columns)
            if columns else '*'
        )
        sql = f"SELECT {select_columns} FROM {quoted_table_name}"
        params = []

        if joins:
            for join_info in joins:
                join_table = self.quote_identifier(join_info['table'])
                join_condition = join_info['condition']
                join_type = join_info.get('type', 'INNER') # Default to INNER JOIN
                sql += f" {join_type} JOIN {join_table} ON {join_condition}"

        if where_condition:
            sql += f" WHERE {' AND '.join(where_condition) if isinstance(where_condition, list) else where_condition}" # Allow list or string
            # Params for WHERE clause would need to be handled based on condition type, skipping for now for simplicity in this base example

        if order_by:
            sql += f" ORDER BY {', '.join(self._quote_order_item(c) for c in order_by)}"

        if limit is not None:
            sql += f" LIMIT {limit}"
        
        if offset is not None:
            sql += f" OFFSET {offset}"

        return sql, tuple(params) # Return empty tuple for params as we aren't handling where params in this basic select


    def quote_identifier(self, identifier: str) -> str:
        if '.' in identifier:
            table, col = identifier.split('.', 1)
            return f'"{table}"."{col}"'
        return f'"{identifier}"'

    def placeholder(self, data_len: int) -> list[str]:
        return [f'${i}' for i in range(1, data_len+1)]
    
    def parser(self, result: tuple):
        rows, columns = result
        column_names = [col["name"] for col in columns]
        return [dict(zip(column_names, row)) for row in rows]
