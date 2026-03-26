from ..abstracts.dialetecs import SQLDialect
from ..abstracts.connection_types import Connection
from ..abstracts.field_types import BaseField, ForeignKeyField
from ..drivers.mysql import MySQLSocketClient
from ...exceptions import ConnectionError as OrmConnectionError
from typing import Dict, List, Any, Tuple, Optional

class MySQLDialect(SQLDialect):
    """Generates SQL for MySQL databases."""
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
                column_definition += f" DEFAULT '{field.default}'" # MySQL uses single quotes for default values
            column_definitions.append(column_definition)

        primary_key_constraint = self.get_primary_key_constraint(primary_keys)
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)}{primary_key_constraint})"

    def get_sql_type(self, field: BaseField) -> str:
        sql_type = field.get_sql_type()
        # INTEGER com primary_key → INT AUTO_INCREMENT no MySQL
        if sql_type in ("INTEGER", "AUTOFIELD") and field.primary_key:
            return "INT AUTO_INCREMENT"
        mapping = {
            "INTEGER":   "INT",
            "SMALLINT":  "SMALLINT",
            "BIGINT":    "BIGINT",
            "AUTOFIELD": "INT AUTO_INCREMENT",
            "TEXT":      "TEXT",
            "REAL":      "FLOAT",
            "DECIMAL":   "DECIMAL",
            "BOOLEAN":   "TINYINT(1)",
            "TIMESTAMP": "DATETIME",
            "JSONB":     "JSON",
            "UUID":      "VARCHAR(36)",
            "BINARY":    "BLOB",
        }
        return mapping.get(sql_type, sql_type)

    def get_primary_key_constraint(self, primary_keys: List[str]) -> str:
        if primary_keys:
            quoted = [self.quote_identifier(k) for k in primary_keys]
            return f", PRIMARY KEY ({', '.join(quoted)})"
        return ""

    def insert(self, table_name: str, data: Dict[str, Any]) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        columns = ', '.join(self.quote_identifier(k) for k in data.keys())
        placeholders = ', '.join(self.placeholder(len(data)))
        sql = f"INSERT INTO {quoted_table} ({columns}) VALUES ({placeholders})"
        return sql, tuple(data.values())

    def update(self, table_name: str, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        set_clause = ', '.join(
            f"{self.quote_identifier(k)} = %s" for k in data.keys()
        )
        sql = f"UPDATE {quoted_table} SET {set_clause} WHERE {where_condition}"
        return sql, tuple(data.values())

    def delete(self, table_name: str, where_condition: str) -> str:
        return f"DELETE FROM {self.quote_identifier(table_name)} WHERE {where_condition}"

    def upsert(
        self,
        table_name: str,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Tuple[str, tuple]:
        """MySQL: INSERT … ON DUPLICATE KEY UPDATE col = VALUES(col) …"""
        quoted_table = self.quote_identifier(table_name)
        cols = list(data.keys())
        quoted_cols = ', '.join(self.quote_identifier(c) for c in cols)
        placeholders = ', '.join(self.placeholder(len(cols)))

        to_update = update_columns or [c for c in cols if c not in conflict_columns]
        set_clause = ', '.join(
            f"{self.quote_identifier(c)} = VALUES({self.quote_identifier(c)})"
            for c in to_update
        )

        sql = (
            f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({placeholders})\n"
            f"ON DUPLICATE KEY UPDATE {set_clause}"
        )
        return sql, tuple(data.values())

    def select(self, table_name: str, columns: List[str],
               where_condition: Optional[str] = None,
               order_by: Optional[List[str]] = None,
               limit: Optional[int] = None,
               offset: Optional[int] = None,
               joins: Optional[List[Dict[str, str]]] = None) -> Tuple[str, tuple]:
        quoted_table = self.quote_identifier(table_name)
        select_cols = ', '.join(
            self.quote_identifier(c) if c != '*' else '*' for c in columns
        ) if columns else '*'
        sql = f"SELECT {select_cols} FROM {quoted_table}"

        if joins:
            for join_info in joins:
                join_table = self.quote_identifier(join_info['table'])
                join_type = join_info.get('type', 'INNER')
                sql += f" {join_type} JOIN {join_table} ON {join_info['condition']}"

        if where_condition:
            sql += f" WHERE {where_condition}"

        if order_by:
            sql += f" ORDER BY {', '.join(self._quote_order_item(c) for c in order_by)}"

        if limit is not None:
            sql += f" LIMIT {limit}"

        if offset is not None:
            sql += f" OFFSET {offset}"

        return sql, ()

    def quote_identifier(self, identifier: str) -> str:
        if '.' in identifier:
            table, col = identifier.split('.', 1)
            return f'`{table}`.`{col}`'
        return f'`{identifier}`'

    def placeholder(self, data_len: int) -> List[str]:
        return ['%s'] * data_len

    def parser(self, result):
        # MySQLSocketClient.run() already returns list[dict]
        return result if result else []


class MySQLConnection(Connection):
    """Conexão MySQL usando MySQLSocketClient (sockets raw)."""

    def connect(self) -> bool:
        try:
            db = MySQLSocketClient(
                host=self.host, port=self.port,
                username=self.user, password=self.password,
                database=self.database,
            )
            if db.connect():
                self._conn = db
                self.dialect = MySQLDialect()
                return True
            return False
        except Exception as e:
            print(f"MySQL connection failed: {e}")
            return False

    def disconnect(self) -> None:
        if self._conn:
            self._conn.disconnect()
            self._conn = None

    def run(self, sql: str, params: Optional[tuple] = None) -> Any:
        if not self._conn:
            raise OrmConnectionError("Conexão MySQL não estabelecida. Chame connect() primeiro.")
        return self._conn.run(sql, params)

    def begin(self) -> None:
        if self._conn:
            self._conn.begin()

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn:
            self._conn.rollback()