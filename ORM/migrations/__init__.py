"""Database migration system for PySocketCommLib ORM."""

from .migration import Migration, MigrationManager
from .operations import (
    CreateTable, DropTable,
    AddColumn, DropColumn, RenameColumn, RenameTable,
    AlterColumn, AddIndex, DropIndex, RunSQL,
)
from .generator import generate_operations
from .inspector import inspect_tables, ColumnInfo

__all__ = [
    "Migration",
    "MigrationManager",
    "CreateTable",
    "DropTable",
    "AddColumn",
    "DropColumn",
    "RenameColumn",
    "RenameTable",
    "AlterColumn",
    "AddIndex",
    "DropIndex",
    "RunSQL",
    "generate_operations",
    "inspect_tables",
    "ColumnInfo",
]
