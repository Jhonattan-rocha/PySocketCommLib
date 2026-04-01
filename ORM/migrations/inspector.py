"""
Schema introspection — reads the current database structure so the
auto-migration generator can diff it against the declared models.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set

from ..abstracts.connection_types import Connection

logger = logging.getLogger(__name__)

# Name of the table used to track applied migrations — always excluded.
_MIGRATION_TABLE = "migrations"


@dataclass
class ColumnInfo:
    """Metadata about a single column returned by the DB introspection."""
    name: str
    sql_type: str       # raw type string as reported by the database
    nullable: bool
    has_default: bool
    is_primary_key: bool


def inspect_tables(connection: Connection) -> Dict[str, Dict[str, ColumnInfo]]:
    """
    Return the live schema of the connected database.

    Returns:
        ``{table_name: {column_name: ColumnInfo}}``

    The migrations tracking table is excluded from the result.
    """
    dialect_name = type(connection.dialect).__name__.lower()

    if "sqlite" in dialect_name:
        return _inspect_sqlite(connection)
    if "postgres" in dialect_name or "psql" in dialect_name:
        return _inspect_psql(connection)
    if "mysql" in dialect_name:
        return _inspect_mysql(connection)

    raise ValueError(
        f"Schema inspection is not supported for dialect '{dialect_name}'."
    )


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def _list_tables_sqlite(connection: Connection) -> List[str]:
    result = connection.run(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    if not result:
        return []
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return [row["name"] for row in result]
    return []


def _inspect_sqlite(connection: Connection) -> Dict[str, Dict[str, ColumnInfo]]:
    tables = [t for t in _list_tables_sqlite(connection) if t != _MIGRATION_TABLE]
    schema: Dict[str, Dict[str, ColumnInfo]] = {}

    for table in tables:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        result = connection.run(f"PRAGMA table_info(\"{table}\")")
        cols: Dict[str, ColumnInfo] = {}
        if isinstance(result, list):
            for row in result:
                if isinstance(row, dict):
                    name = row["name"]
                    cols[name] = ColumnInfo(
                        name=name,
                        sql_type=str(row.get("type", "")).upper(),
                        nullable=not bool(row.get("notnull", 0)),
                        has_default=row.get("dflt_value") is not None,
                        is_primary_key=bool(row.get("pk", 0)),
                    )
        schema[table] = cols
        logger.debug("Inspected SQLite table '%s': %d columns", table, len(cols))

    return schema


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

def _list_tables_psql(connection: Connection) -> List[str]:
    result = connection.run(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    if not result:
        return []
    # PsqlConnection.run() may return (rows, cols) tuple
    if isinstance(result, tuple):
        rows, cols = result
        idx = 0
        if cols:
            col_names = [c["name"] if isinstance(c, dict) else c for c in cols]
            if "tablename" in col_names:
                idx = col_names.index("tablename")
        return [row[idx] for row in rows]
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return [row["tablename"] for row in result]
    return []


def _inspect_psql(connection: Connection) -> Dict[str, Dict[str, ColumnInfo]]:
    tables = [t for t in _list_tables_psql(connection) if t != _MIGRATION_TABLE]
    schema: Dict[str, Dict[str, ColumnInfo]] = {}

    for table in tables:
        sql = (
            "SELECT column_name, data_type, is_nullable, column_default, "
            "CASE WHEN kcu.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_pk "
            "FROM information_schema.columns c "
            "LEFT JOIN information_schema.key_column_usage kcu "
            "  ON c.table_name = kcu.table_name "
            "  AND c.column_name = kcu.column_name "
            "  AND kcu.constraint_name IN ("
            "    SELECT constraint_name FROM information_schema.table_constraints "
            "    WHERE table_name = $1 AND constraint_type = 'PRIMARY KEY'"
            "  ) "
            "WHERE c.table_name = $1 AND c.table_schema = 'public'"
        )
        result = connection.run(sql, (table,))
        cols: Dict[str, ColumnInfo] = {}

        rows_data = []
        if isinstance(result, tuple):
            raw_rows, raw_cols = result
            col_names = [c["name"] if isinstance(c, dict) else c for c in raw_cols]
            rows_data = [dict(zip(col_names, row)) for row in raw_rows]
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            rows_data = result

        for row in rows_data:
            name = row["column_name"]
            cols[name] = ColumnInfo(
                name=name,
                sql_type=str(row.get("data_type", "")).upper(),
                nullable=str(row.get("is_nullable", "YES")).upper() == "YES",
                has_default=row.get("column_default") is not None,
                is_primary_key=bool(row.get("is_pk", False)),
            )
        schema[table] = cols
        logger.debug("Inspected PostgreSQL table '%s': %d columns", table, len(cols))

    return schema


# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

def _list_tables_mysql(connection: Connection) -> List[str]:
    result = connection.run("SHOW TABLES")
    if not result:
        return []
    if isinstance(result, list) and result:
        row = result[0]
        if isinstance(row, dict):
            key = list(row.keys())[0]
            return [r[key] for r in result]
    return []


def _inspect_mysql(connection: Connection) -> Dict[str, Dict[str, ColumnInfo]]:
    tables = [t for t in _list_tables_mysql(connection) if t != _MIGRATION_TABLE]
    schema: Dict[str, Dict[str, ColumnInfo]] = {}

    for table in tables:
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_NAME = %s AND TABLE_SCHEMA = DATABASE() "
            "ORDER BY ORDINAL_POSITION"
        )
        result = connection.run(sql, (table,))
        cols: Dict[str, ColumnInfo] = {}
        if isinstance(result, list):
            for row in result:
                if isinstance(row, dict):
                    name = row["COLUMN_NAME"]
                    cols[name] = ColumnInfo(
                        name=name,
                        sql_type=str(row.get("DATA_TYPE", "")).upper(),
                        nullable=str(row.get("IS_NULLABLE", "YES")).upper() == "YES",
                        has_default=row.get("COLUMN_DEFAULT") is not None,
                        is_primary_key=str(row.get("COLUMN_KEY", "")).upper() == "PRI",
                    )
        schema[table] = cols
        logger.debug("Inspected MySQL table '%s': %d columns", table, len(cols))

    return schema
