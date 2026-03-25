"""Database migration operations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..abstracts.dialetecs import SQLDialect
from ..abstracts.field_types import BaseField


class Operation(ABC):
    """Base class for migration operations."""

    @abstractmethod
    def get_sql(self, dialect: SQLDialect) -> str:
        """Generate SQL for this operation using the given dialect.

        May return multiple statements separated by semicolons when needed
        (e.g. AlterColumn on PostgreSQL).
        """
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

    def _primary_keys_from_fields(self, fields: Dict[str, BaseField]) -> List[str]:
        """Extract names of primary-key fields."""
        return [
            (f.db_column_name or name)
            for name, f in fields.items()
            if getattr(f, 'primary_key', False)
        ]


class CreateTable(Operation):
    """Create a new table."""

    def __init__(self, table_name: str, fields: Dict[str, BaseField],
                 primary_keys: Optional[List[str]] = None):
        self.table_name = table_name
        self.fields = fields
        # Allow explicit primary_keys or auto-detect from field.primary_key
        self.primary_keys = primary_keys if primary_keys is not None else self._primary_keys_from_fields(fields)

    def get_sql(self, dialect: SQLDialect) -> str:
        col_defs = [
            self._field_definition(dialect, name, field)
            for name, field in self.fields.items()
        ]
        quoted_table = dialect.quote_identifier(self.table_name)
        pk_constraint = dialect.get_primary_key_constraint(self.primary_keys)
        return f"CREATE TABLE IF NOT EXISTS {quoted_table} ({', '.join(col_defs)}{pk_constraint})"

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
            raise ValueError("Cannot reverse DROP TABLE without field definitions.")
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
            raise ValueError("Cannot reverse DROP COLUMN without the field definition.")
        return AddColumn(self.table_name, self.column_name, self.field)


class RenameColumn(Operation):
    """Rename a column (PostgreSQL, MySQL 8+, SQLite 3.25+)."""

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
        # Swap old ↔ new to undo the rename
        return RenameColumn(self.table_name, self.new_name, self.old_name)


class RenameTable(Operation):
    """Rename an existing table."""

    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name

    def get_sql(self, dialect: SQLDialect) -> str:
        dialect_name = type(dialect).__name__.lower()
        quoted_old = dialect.quote_identifier(self.old_name)
        quoted_new = dialect.quote_identifier(self.new_name)
        if "mysql" in dialect_name:
            return f"RENAME TABLE {quoted_old} TO {quoted_new}"
        # PostgreSQL and SQLite
        return f"ALTER TABLE {quoted_old} RENAME TO {quoted_new}"

    def get_reverse_operation(self) -> 'RenameTable':
        return RenameTable(self.new_name, self.old_name)


class AlterColumn(Operation):
    """Change a column's type or constraints.

    PostgreSQL: emits separate statements for TYPE, NULL/NOT NULL, and DEFAULT,
    joined by semicolons. Execute each statement individually via
    ``for stmt in op.get_sql(dialect).split(';') if stmt.strip()``.

    MySQL: uses MODIFY COLUMN with the full column definition.

    SQLite: ALTER COLUMN is not supported natively — a comment is returned.
    """

    def __init__(self, table_name: str, column_name: str,
                 old_field: BaseField, new_field: BaseField):
        self.table_name = table_name
        self.column_name = column_name
        self.old_field = old_field
        self.new_field = new_field

    def get_sql(self, dialect: SQLDialect) -> str:
        dialect_name = type(dialect).__name__.lower()
        quoted_table = dialect.quote_identifier(self.table_name)
        quoted_col = dialect.quote_identifier(self.column_name)
        new_sql_type = dialect.get_sql_type(self.new_field)

        if "postgres" in dialect_name or "psql" in dialect_name:
            stmts = [
                f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} TYPE {new_sql_type}",
            ]
            if not self.new_field.nullable:
                stmts.append(
                    f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} SET NOT NULL"
                )
            else:
                stmts.append(
                    f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} DROP NOT NULL"
                )
            if self.new_field.default is not None:
                default_val = (
                    f"'{self.new_field.default}'"
                    if isinstance(self.new_field.default, str)
                    else self.new_field.default
                )
                stmts.append(
                    f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} SET DEFAULT {default_val}"
                )
            else:
                stmts.append(
                    f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} DROP DEFAULT"
                )
            return ";\n".join(stmts)

        elif "mysql" in dialect_name:
            col_def = self._field_definition(dialect, self.column_name, self.new_field)
            return f"ALTER TABLE {quoted_table} MODIFY COLUMN {col_def}"

        else:
            # SQLite does not support ALTER COLUMN natively
            return (
                f"-- SQLite does not support ALTER COLUMN: "
                f"{self.table_name}.{self.column_name} — "
                f"recreate the table manually."
            )

    def get_reverse_operation(self) -> 'AlterColumn':
        return AlterColumn(
            self.table_name, self.column_name,
            old_field=self.new_field, new_field=self.old_field,
        )


class AddIndex(Operation):
    """Create an index on one or more columns."""

    def __init__(self, table_name: str, columns: List[str],
                 index_name: Optional[str] = None, unique: bool = False):
        self.table_name = table_name
        self.columns = columns
        self.unique = unique
        self.index_name = index_name or f"idx_{table_name}_{'_'.join(columns)}"

    def get_sql(self, dialect: SQLDialect) -> str:
        unique_kw = "UNIQUE " if self.unique else ""
        quoted_index = dialect.quote_identifier(self.index_name)
        quoted_table = dialect.quote_identifier(self.table_name)
        quoted_cols = ", ".join(dialect.quote_identifier(c) for c in self.columns)
        return (
            f"CREATE {unique_kw}INDEX IF NOT EXISTS {quoted_index} "
            f"ON {quoted_table} ({quoted_cols})"
        )

    def get_reverse_operation(self) -> 'DropIndex':
        return DropIndex(self.table_name, self.index_name)


class DropIndex(Operation):
    """Drop an index."""

    def __init__(self, table_name: str, index_name: str):
        self.table_name = table_name
        self.index_name = index_name

    def get_sql(self, dialect: SQLDialect) -> str:
        dialect_name = type(dialect).__name__.lower()
        quoted_index = dialect.quote_identifier(self.index_name)
        if "mysql" in dialect_name:
            quoted_table = dialect.quote_identifier(self.table_name)
            return f"DROP INDEX {quoted_index} ON {quoted_table}"
        # PostgreSQL and SQLite
        return f"DROP INDEX IF EXISTS {quoted_index}"

    def get_reverse_operation(self) -> Operation:
        raise ValueError(
            "Cannot reverse DROP INDEX without the original column list — "
            "use AddIndex explicitly."
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
            raise ValueError("RunSQL without reverse_sql cannot be reversed.")
        return RunSQL(self.reverse_sql, self.sql)
