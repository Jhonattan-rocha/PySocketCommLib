"""Database migration management system."""

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .operations import Operation
from ..abstracts.connection_types import Connection
from ...exceptions import UnmetDependencyError, CircularDependencyError, MigrationError


class Migration:
    """Represents a single database migration."""

    def __init__(self, name: str, operations: List[Operation],
                 dependencies: Optional[List[str]] = None):
        self.name = name
        self.operations = operations
        self.dependencies = dependencies or []
        self.timestamp = datetime.now().isoformat()
        self.hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        content = f"{self.name}:{len(self.operations)}:{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def apply(self, connection: Connection) -> None:
        """Aplica todas as operações da migration."""
        dialect = connection.dialect
        for operation in self.operations:
            sql = operation.get_sql(dialect)
            if not sql or sql.startswith('--'):
                continue
            try:
                for stmt in sql.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        connection.run(stmt)
            except Exception as exc:
                raise MigrationError(
                    f"Falha ao aplicar '{self.name}': {exc}"
                ) from exc

    def rollback(self, connection: Connection) -> None:
        """Desfaz as operações da migration em ordem inversa."""
        dialect = connection.dialect
        for operation in reversed(self.operations):
            reverse_op = operation.get_reverse_operation()
            sql = reverse_op.get_sql(dialect)
            if not sql or sql.startswith('--'):
                continue
            try:
                for stmt in sql.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        connection.run(stmt)
            except Exception as exc:
                raise MigrationError(
                    f"Falha ao reverter '{self.name}': {exc}"
                ) from exc

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'timestamp': self.timestamp,
            'hash': self.hash,
            'dependencies': self.dependencies,
            'operations_count': len(self.operations),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any],
                  operations: List[Operation]) -> 'Migration':
        migration = cls(data['name'], operations, data.get('dependencies', []))
        migration.timestamp = data['timestamp']
        migration.hash = data['hash']
        return migration


class MigrationManager:
    """
    Gerencia a aplicação e reversão de migrations.

    Usa a `connection` já existente (com `.dialect` configurado),
    portanto funciona com PostgreSQL, MySQL e SQLite sem configuração extra.

    Exemplo::

        conn = SqliteConnection("mydb.sqlite3")
        conn.connect()

        manager = MigrationManager(conn)
        manager.apply_migrations([
            Migration("create_users", [
                CreateTable("users", {"id": IntegerField(primary_key=True), ...})
            ])
        ])
    """

    MIGRATION_TABLE = "migrations"

    def __init__(self, connection: Connection,
                 migrations_dir: str = "migrations"):
        self.connection = connection
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(exist_ok=True)
        self._ensure_migration_table()

    # ------------------------------------------------------------------
    # Migration tracking table
    # ------------------------------------------------------------------

    def _ensure_migration_table(self) -> None:
        dialect_name = type(self.connection.dialect).__name__.lower()

        if "postgres" in dialect_name or "psql" in dialect_name:
            pk_type = "SERIAL PRIMARY KEY"
        elif "mysql" in dialect_name:
            pk_type = "INT AUTO_INCREMENT PRIMARY KEY"
        else:
            pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT"

        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.MIGRATION_TABLE} (
            id {pk_type},
            name VARCHAR(255) UNIQUE NOT NULL,
            hash VARCHAR(32) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dependencies TEXT
        )
        """.strip()
        self.connection.run(sql)

    # ------------------------------------------------------------------
    # Querying applied migrations
    # ------------------------------------------------------------------

    def get_applied_migrations(self) -> List[str]:
        """Retorna os nomes das migrations já aplicadas, em ordem."""
        result = self.connection.run(
            f"SELECT name FROM {self.MIGRATION_TABLE} ORDER BY applied_at"
        )
        if not result:
            return []
        # connection.run pode retornar list[dict] (SQLite/MySQL) ou (rows, cols) (Psql raw)
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return [row['name'] for row in result]
        if isinstance(result, tuple):  # PostgreSQL driver raw: (rows, cols)
            rows, cols = result
            col_names = [c['name'] if isinstance(c, dict) else c for c in cols]
            idx = col_names.index('name') if 'name' in col_names else 0
            return [row[idx] for row in rows]
        return []

    def get_pending_migrations(self,
                               available: List[Migration]) -> List[Migration]:
        applied = set(self.get_applied_migrations())
        return [m for m in available if m.name not in applied]

    # ------------------------------------------------------------------
    # Apply / Rollback
    # ------------------------------------------------------------------

    def apply_migration(self, migration: Migration) -> None:
        applied = set(self.get_applied_migrations())
        for dep in migration.dependencies:
            if dep not in applied:
                raise UnmetDependencyError(migration.name, dep)

        migration.apply(self.connection)
        self._record_migration(migration)
        print(f"[migration] Aplicada: {migration.name}")

    def rollback_migration(self, migration: Migration) -> None:
        migration.rollback(self.connection)
        self._delete_migration_record(migration.name)
        print(f"[migration] Revertida: {migration.name}")

    def apply_migrations(self, migrations: List[Migration]) -> None:
        pending = self.get_pending_migrations(migrations)
        if not pending:
            print("[migration] Nenhuma migration pendente.")
            return
        for m in self._sort_by_dependencies(pending):
            self.apply_migration(m)

    def rollback_migrations(self, migrations: List[Migration],
                            count: int = 1) -> None:
        applied = self.get_applied_migrations()
        if not applied:
            print("[migration] Nenhuma migration para reverter.")
            return
        migration_map = {m.name: m for m in migrations}
        for name in reversed(applied[-count:]):
            if name in migration_map:
                self.rollback_migration(migration_map[name])
            else:
                print(f"[migration] Aviso: '{name}' não encontrada nas migrations disponíveis.")

    # ------------------------------------------------------------------
    # Record keeping (dialect-aware placeholders)
    # ------------------------------------------------------------------

    def _record_migration(self, migration: Migration) -> None:
        placeholders = self.connection.dialect.placeholder(3)
        sql = (
            f"INSERT INTO {self.MIGRATION_TABLE} (name, hash, dependencies) "
            f"VALUES ({', '.join(placeholders)})"
        )
        self.connection.run(
            sql,
            (migration.name, migration.hash, json.dumps(migration.dependencies)),
        )

    def _delete_migration_record(self, name: str) -> None:
        placeholder = self.connection.dialect.placeholder(1)[0]
        sql = f"DELETE FROM {self.MIGRATION_TABLE} WHERE name = {placeholder}"
        self.connection.run(sql, (name,))

    # ------------------------------------------------------------------
    # Dependency sorting (topological)
    # ------------------------------------------------------------------

    def _sort_by_dependencies(self,
                               migrations: List[Migration]) -> List[Migration]:
        sorted_migrations: List[Migration] = []
        remaining = list(migrations)
        applied = set(self.get_applied_migrations())

        while remaining:
            ready = [
                m for m in remaining
                if all(
                    dep in applied or any(s.name == dep for s in sorted_migrations)
                    for dep in m.dependencies
                )
            ]
            if not ready:
                names = [m.name for m in remaining]
                raise CircularDependencyError(names)
            for m in ready:
                sorted_migrations.append(m)
                remaining.remove(m)

        return sorted_migrations

    # ------------------------------------------------------------------
    # File generation
    # ------------------------------------------------------------------

    def create_migration_file(self, name: str,
                               dependencies: Optional[List[str]] = None) -> str:
        """Gera um arquivo de migration vazio pronto para preencher."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.py"
        filepath = self.migrations_dir / filename
        deps_repr = repr(dependencies or [])

        content = f'''"""Migration: {name}

Generated: {datetime.now().isoformat()}
"""

from PySocketCommLib.ORM.migrations.operations import (
    CreateTable, DropTable, AddColumn, DropColumn,
    RenameColumn, AlterColumn, RunSQL,
)
from PySocketCommLib.ORM.migrations.migration import Migration
from PySocketCommLib.ORM.abstracts.field_types import (
    IntegerField, TextField, FloatField, BooleanField,
    DateTimeField, DecimalField, ForeignKeyField,
)

operations = [
    # Adicione suas operações aqui. Exemplos:
    # CreateTable("users", {{
    #     "id": IntegerField(primary_key=True),
    #     "name": TextField(nullable=False),
    #     "email": TextField(unique=True),
    # }}),
    # AddColumn("users", "phone", TextField(nullable=True)),
]

dependencies = {deps_repr}

migration = Migration("{name}", operations, dependencies)
'''
        filepath.write_text(content, encoding='utf-8')
        print(f"[migration] Arquivo criado: {filepath}")
        return str(filepath)

    def load_migrations_from_directory(self) -> List[Migration]:
        """Carrega todas as migrations do diretório."""
        migrations = []
        for file_path in sorted(self.migrations_dir.glob("*.py")):
            if file_path.name.startswith("__"):
                continue
            try:
                spec = importlib.util.spec_from_file_location("migration", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'migration'):
                    migrations.append(module.migration)
            except Exception as e:
                print(f"[migration] Falha ao carregar {file_path}: {e}")
        return migrations
