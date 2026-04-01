"""
Auto-migration generator — compares the live database schema against
declared models and produces a list of Operations to bring the DB in sync.
"""

import logging
from typing import Dict, List, Optional, Type, TYPE_CHECKING

from .inspector import inspect_tables, ColumnInfo
from .operations import (
    Operation, CreateTable, DropTable, AddColumn, DropColumn, AlterColumn,
)
from ..abstracts.field_types import BaseField
from ..abstracts.connection_types import Connection

if TYPE_CHECKING:
    from ..models.model import BaseModel

logger = logging.getLogger(__name__)


def _fields_for_model(model_cls: "Type[BaseModel]") -> Dict[str, BaseField]:
    """
    Return ``{attribute_name: field_instance}`` for all ``BaseField``
    attributes declared on the model class (including inherited ones).
    """
    fields: Dict[str, BaseField] = {}
    for klass in reversed(model_cls.__mro__):
        for attr, val in vars(klass).items():
            if isinstance(val, BaseField):
                fields[attr] = val
    return fields


def _col_name(attr_name: str, field: BaseField) -> str:
    """Resolve the DB column name for a model field."""
    return field.db_column_name if field.db_column_name else attr_name


def _types_compatible(db_type: str, field: BaseField) -> bool:
    """
    Rough check: does the stored SQL type match what the field would generate?

    We only compare the *base* type keyword (e.g. ``TEXT``, ``INTEGER``)
    because dialects may produce ``VARCHAR(255)`` while the DB reports ``VARCHAR``.
    """
    declared = field.get_sql_type().upper()
    db = db_type.upper()

    # Exact match
    if db == declared:
        return True

    # Strip parenthetical modifiers: VARCHAR(255) → VARCHAR
    import re
    declared_base = re.sub(r"\(.*\)", "", declared).strip()
    db_base = re.sub(r"\(.*\)", "", db).strip()

    if db_base == declared_base:
        return True

    # Known aliases / DB-specific expansions
    aliases = {
        "INT": {"INTEGER", "INT", "INT4"},
        "INTEGER": {"INTEGER", "INT", "INT4"},
        "BIGINT": {"BIGINT", "INT8"},
        "SMALLINT": {"SMALLINT", "INT2"},
        "TEXT": {"TEXT", "CLOB", "LONGTEXT", "MEDIUMTEXT"},
        "VARCHAR": {"VARCHAR", "CHARACTER VARYING"},
        "BOOLEAN": {"BOOLEAN", "BOOL", "TINYINT"},
        "FLOAT": {"FLOAT", "REAL", "FLOAT4"},
        "DOUBLE": {"DOUBLE", "DOUBLE PRECISION", "FLOAT8"},
        "DECIMAL": {"DECIMAL", "NUMERIC"},
        "DATETIME": {"DATETIME", "TIMESTAMP"},
        "BLOB": {"BLOB", "BYTEA", "BINARY", "LONGBLOB"},
        "UUID": {"UUID", "CHAR(36)", "VARCHAR(36)"},
        "JSON": {"JSON", "JSONB"},
    }

    for canonical, group in aliases.items():
        if declared_base in group and db_base in group:
            return True

    return False


def generate_operations(
    connection: Connection,
    models: List["Type[BaseModel]"],
    drop_tables: bool = False,
    drop_columns: bool = False,
) -> List[Operation]:
    """
    Compare live DB schema against *models* and return the Operations needed
    to migrate the DB to match the models.

    Args:
        connection:   Active DB connection (used for introspection).
        models:       List of ``BaseModel`` subclasses to compare against.
        drop_tables:  If ``True``, emit ``DropTable`` for tables in the DB
                      that have no corresponding model.  Defaults to ``False``
                      (safe default — prevents accidental data loss).
        drop_columns: If ``True``, emit ``DropColumn`` for columns in the DB
                      that have no corresponding field in the model.  Defaults
                      to ``False``.

    Returns:
        List of :class:`Operation` instances in application order.
    """
    db_schema = inspect_tables(connection)
    ops: List[Operation] = []

    # Build a map of table_name → model class
    model_map: Dict[str, "Type[BaseModel]"] = {}
    for model_cls in models:
        table = getattr(model_cls, "__tablename__", None) or _infer_table_name(model_cls)
        model_map[table] = model_cls

    # --- 1. Tables that exist in models but not in DB → CreateTable ---
    for table, model_cls in model_map.items():
        if table not in db_schema:
            fields = _fields_for_model(model_cls)
            logger.debug("Table '%s' not found in DB — will CREATE.", table)
            ops.append(CreateTable(table, fields))

    # --- 2. Tables that exist in both → diff columns ---
    for table, model_cls in model_map.items():
        if table not in db_schema:
            continue  # already handled above

        db_cols: Dict[str, ColumnInfo] = db_schema[table]
        model_fields = _fields_for_model(model_cls)

        # Map col_name → (attr_name, field)
        model_col_map: Dict[str, tuple] = {
            _col_name(attr, field): (attr, field)
            for attr, field in model_fields.items()
        }

        # 2a. Columns in model but not in DB → AddColumn
        for col_name, (attr_name, field) in model_col_map.items():
            if col_name not in db_cols:
                logger.debug(
                    "Column '%s.%s' missing in DB — will ADD.", table, col_name
                )
                ops.append(AddColumn(table, attr_name, field))

        # 2b. Columns in both — check for type changes → AlterColumn
        for col_name, (attr_name, field) in model_col_map.items():
            if col_name not in db_cols:
                continue  # handled above
            db_col = db_cols[col_name]
            if not _types_compatible(db_col.sql_type, field):
                logger.debug(
                    "Column '%s.%s' type mismatch (DB=%s, model=%s) — will ALTER.",
                    table, col_name, db_col.sql_type, field.get_sql_type(),
                )
                # Build a minimal "old" field to represent current DB state.
                # We only use it for the rollback SQL, so sql_type accuracy matters.
                from ..abstracts.field_types import TextField  # late import avoids circulars
                old_field = _make_db_field(db_col)
                ops.append(
                    AlterColumn(
                        table, attr_name, old_field, field,
                        all_fields=model_fields,
                    )
                )

        # 2c. Columns in DB but not in model → DropColumn (opt-in)
        if drop_columns:
            for col_name in db_cols:
                if col_name not in model_col_map:
                    logger.debug(
                        "Column '%s.%s' in DB but not in model — will DROP.",
                        table, col_name,
                    )
                    ops.append(DropColumn(table, col_name))

    # --- 3. Tables in DB but not in models → DropTable (opt-in) ---
    if drop_tables:
        for table in db_schema:
            if table not in model_map:
                logger.debug(
                    "Table '%s' in DB but has no model — will DROP.", table
                )
                ops.append(DropTable(table))

    return ops


def _infer_table_name(model_cls: type) -> str:
    """Derive a table name from the class name (lowercase, e.g. ``UserProfile`` → ``userprofile``)."""
    return model_cls.__name__.lower()


def _make_db_field(col: ColumnInfo) -> BaseField:
    """
    Build a minimal ``BaseField``-compatible object from a ``ColumnInfo``
    so that ``AlterColumn`` can generate rollback SQL.

    We use a simple anonymous subclass that stores the raw sql_type.
    """

    class _RawField(BaseField):
        def __init__(self, sql_type: str, nullable: bool, has_default: bool, pk: bool):
            super().__init__(
                nullable=nullable,
                primary_key=pk,
            )
            self._sql_type = sql_type
            self.has_default = has_default

        def get_sql_type(self) -> str:
            return self._sql_type

    return _RawField(
        sql_type=col.sql_type,
        nullable=col.nullable,
        has_default=col.has_default,
        pk=col.is_primary_key,
    )
