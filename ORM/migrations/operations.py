"""Database migration operations."""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..abstracts.dialetecs import SQLDialect
from ..abstracts.field_types import BaseField


class Operation(ABC):
    """Base class for migration operations."""

    @abstractmethod
    def get_sql(self, dialect: SQLDialect) -> str:
        """Generate SQL for this operation using the given dialect."""
        pass

    @abstractmethod
    def get_reverse_operation(self) -> 'Operation':
        """Return the inverse operation for rollback."""
        pass

    def _field_definition(self, dialect: SQLDialect, field_name: str, field: BaseField) -> str:
        """Build a column definition string using the dialect."""
        db_name = field.db_column_name if field.db_column_name else field_name
        col = dialect.quote_identifier(db_name)
        sql_type = dialect.get_sql_type(field)
        parts = [f"{col} {sql_type}"]
        if not field.nullable:
            parts.append("NOT NULL")
        if field.unique:
            parts.append("UNIQUE")
        if field.default is not None:
            if isinstance(field.default, str):
                parts.append(f"DEFAULT '{field.default}'")
            else:
                parts.append(f"DEFAULT {field.default}")
        return " ".join(parts)


class CreateTable(Operation):
    """Create a new table."""

    def __init__(self, table_name: str, fields: Dict[str, BaseField]):
        self.table_name = table_name
        self.fields = fields

    def get_sql(self, dialect: SQLDialect) -> str:
        col_defs = [
            self._field_definition(dialect, name, field)
            for name, field in self.fields.items()
        ]
        quoted_table = dialect.quote_identifier(self.table_name)
        return f"CREATE TABLE IF NOT EXISTS {quoted_table} ({', '.join(col_defs)})"

    def get_reverse_operation(self) -> 'DropTable':
        return DropTable(self.table_name, fields=self.fields)


class DropTable(Operation):
    """Drop an existing table."""

    def __init__(self, table_name: str,
                 fields: Optional[Dict[str, BaseField]] = None):
        self.table_name = table_name
        self.fields = fields or {}

    def get_sql(self, dialect: SQLDialect) -> str:
        return f"DROP TABLE IF EXISTS {dialect.quote_identifier(self.table_name)}"

    def get_reverse_operation(self) -> CreateTable:
        if not self.fields:
            raise ValueError("Não é possível reverter DROP TABLE sem a definição dos campos.")
        return CreateTable(self.table_name, self.fields)


class AddColumn(Operation):
    """Add a column to an existing table."""

    def __init__(self, table_name: str, column_name: str, field: BaseField):
        self.table_name = table_name
        self.column_name = column_name
        self.field = field

    def get_sql(self, dialect: SQLDialect) -> str:
        col_def = self._field_definition(dialect, self.column_name, self.field)
        quoted_table = dialect.quote_identifier(self.table_name)
        return f"ALTER TABLE {quoted_table} ADD COLUMN {col_def}"

    def get_reverse_operation(self) -> 'DropColumn':
        return DropColumn(self.table_name, self.column_name, field=self.field)


class DropColumn(Operation):
    """Drop a column from an existing table."""

    def __init__(self, table_name: str, column_name: str,
                 field: Optional[BaseField] = None):
        self.table_name = table_name
        self.column_name = column_name
        self.field = field

    def get_sql(self, dialect: SQLDialect) -> str:
        quoted_table = dialect.quote_identifier(self.table_name)
        quoted_col = dialect.quote_identifier(self.column_name)
        return f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_col}"

    def get_reverse_operation(self) -> AddColumn:
        if not self.field:
            raise ValueError("Não é possível reverter DROP COLUMN sem a definição do campo.")
        return AddColumn(self.table_name, self.column_name, self.field)


class RenameColumn(Operation):
    """Rename a column (supported on PostgreSQL, MySQL 8+, SQLite 3.25+)."""

    def __init__(self, table_name: str, old_name: str, new_name: str):
        self.table_name = table_name
        self.old_name = old_name
        self.new_name = new_name

    def get_sql(self, dialect: SQLDialect) -> str:
        quoted_table = dialect.quote_identifier(self.table_name)
        quoted_old = dialect.quote_identifier(self.old_name)
        quoted_new = dialect.quote_identifier(self.new_name)
        return (
            f"ALTER TABLE {quoted_table} "
            f"RENAME COLUMN {quoted_old} TO {quoted_new}"
        )

    def get_reverse_operation(self) -> 'RenameColumn':
        return RenameColumn(self.table_name, self.old_name, self.new_name)


class AlterColumn(Operation):
    """Change a column's type or constraints."""

    def __init__(self, table_name: str, column_name: str,
                 old_field: BaseField, new_field: BaseField):
        self.table_name = table_name
        self.column_name = column_name
        self.old_field = old_field
        self.new_field = new_field

    def get_sql(self, dialect: SQLDialect) -> str:
        dialect_name = type(dialect).__name__.lower()
        quoted_table = dialect.quote_identifier(self.table_name)
        col_def = self._field_definition(dialect, self.column_name, self.new_field)

        if "postgres" in dialect_name or "psql" in dialect_name:
            return f"ALTER TABLE {quoted_table} ALTER COLUMN {col_def}"
        elif "mysql" in dialect_name:
            return f"ALTER TABLE {quoted_table} MODIFY COLUMN {col_def}"
        else:
            # SQLite não suporta ALTER COLUMN nativamente
            return (
                f"-- SQLite não suporta ALTER COLUMN: "
                f"{self.table_name}.{self.column_name}"
            )

    def get_reverse_operation(self) -> 'AlterColumn':
        return AlterColumn(
            self.table_name, self.column_name,
            old_field=self.new_field, new_field=self.old_field,
        )


class RunSQL(Operation):
    """Execute raw SQL — use only when no other operation fits."""

    def __init__(self, sql: str, reverse_sql: str = ""):
        self.sql = sql
        self.reverse_sql = reverse_sql

    def get_sql(self, dialect: SQLDialect) -> str:
        return self.sql

    def get_reverse_operation(self) -> 'RunSQL':
        if not self.reverse_sql:
            raise ValueError("RunSQL sem reverse_sql não pode ser revertido.")
        return RunSQL(self.reverse_sql, self.sql)
