"""Database migration management system."""

import os
import json
import hashlib
import importlib.util
from datetime import datetime
from typing import List, Dict, Any, Optional, Type
from pathlib import Path

from .operations import Operation
from ..connections.connection_types import ConnectionType


class Migration:
    """Represents a single database migration."""
    
    def __init__(self, name: str, operations: List[Operation], 
                 dependencies: Optional[List[str]] = None):
        """Initialize migration.
        
        Args:
            name: Migration name
            operations: List of operations to perform
            dependencies: List of migration names this depends on
        """
        self.name = name
        self.operations = operations
        self.dependencies = dependencies or []
        self.timestamp = datetime.now().isoformat()
        self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate hash of migration content.
        
        Returns:
            SHA256 hash of migration operations
        """
        content = f"{self.name}:{len(self.operations)}:{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def apply(self, connection: ConnectionType, dialect: str) -> None:
        """Apply migration operations.
        
        Args:
            connection: Database connection
            dialect: Database dialect
        """
        for operation in self.operations:
            sql = operation.get_sql(dialect)
            if sql and not sql.startswith('--'):
                connection.execute(sql)
    
    def rollback(self, connection: ConnectionType, dialect: str) -> None:
        """Rollback migration operations.
        
        Args:
            connection: Database connection
            dialect: Database dialect
        """
        # Apply reverse operations in reverse order
        for operation in reversed(self.operations):
            reverse_op = operation.get_reverse_operation()
            sql = reverse_op.get_sql(dialect)
            if sql and not sql.startswith('--'):
                connection.execute(sql)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert migration to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'timestamp': self.timestamp,
            'hash': self.hash,
            'dependencies': self.dependencies,
            'operations_count': len(self.operations)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], operations: List[Operation]) -> 'Migration':
        """Create migration from dictionary.
        
        Args:
            data: Dictionary data
            operations: List of operations
            
        Returns:
            Migration instance
        """
        migration = cls(data['name'], operations, data.get('dependencies', []))
        migration.timestamp = data['timestamp']
        migration.hash = data['hash']
        return migration


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self, connection: ConnectionType, dialect: str, 
                 migrations_dir: str = "migrations"):
        """Initialize migration manager.
        
        Args:
            connection: Database connection
            dialect: Database dialect
            migrations_dir: Directory containing migration files
        """
        self.connection = connection
        self.dialect = dialect
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(exist_ok=True)
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Ensure migration tracking table exists."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            hash VARCHAR(32) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dependencies TEXT
        )
        """
        
        if self.dialect.lower() == 'postgresql':
            create_table_sql = create_table_sql.replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY')
        elif self.dialect.lower() == 'mysql':
            create_table_sql = create_table_sql.replace('INTEGER PRIMARY KEY', 'INT AUTO_INCREMENT PRIMARY KEY')
        
        self.connection.execute(create_table_sql)
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration names.
        
        Returns:
            List of applied migration names
        """
        result = self.connection.execute("SELECT name FROM migrations ORDER BY applied_at")
        return [row[0] for row in result] if result else []
    
    def get_pending_migrations(self, available_migrations: List[Migration]) -> List[Migration]:
        """Get list of pending migrations.
        
        Args:
            available_migrations: List of available migrations
            
        Returns:
            List of pending migrations
        """
        applied = set(self.get_applied_migrations())
        return [m for m in available_migrations if m.name not in applied]
    
    def apply_migration(self, migration: Migration) -> None:
        """Apply a single migration.
        
        Args:
            migration: Migration to apply
        """
        # Check dependencies
        applied = set(self.get_applied_migrations())
        for dep in migration.dependencies:
            if dep not in applied:
                raise ValueError(f"Migration {migration.name} depends on {dep} which is not applied")
        
        # Apply migration
        try:
            migration.apply(self.connection, self.dialect)
            
            # Record migration
            self.connection.execute(
                "INSERT INTO migrations (name, hash, dependencies) VALUES (?, ?, ?)",
                (migration.name, migration.hash, json.dumps(migration.dependencies))
            )
            
            print(f"Applied migration: {migration.name}")
            
        except Exception as e:
            print(f"Failed to apply migration {migration.name}: {e}")
            raise
    
    def rollback_migration(self, migration: Migration) -> None:
        """Rollback a single migration.
        
        Args:
            migration: Migration to rollback
        """
        try:
            migration.rollback(self.connection, self.dialect)
            
            # Remove migration record
            self.connection.execute(
                "DELETE FROM migrations WHERE name = ?",
                (migration.name,)
            )
            
            print(f"Rolled back migration: {migration.name}")
            
        except Exception as e:
            print(f"Failed to rollback migration {migration.name}: {e}")
            raise
    
    def apply_migrations(self, migrations: List[Migration]) -> None:
        """Apply multiple migrations in order.
        
        Args:
            migrations: List of migrations to apply
        """
        pending = self.get_pending_migrations(migrations)
        
        if not pending:
            print("No pending migrations")
            return
        
        # Sort by dependencies
        sorted_migrations = self._sort_by_dependencies(pending)
        
        for migration in sorted_migrations:
            self.apply_migration(migration)
    
    def rollback_migrations(self, migrations: List[Migration], count: int = 1) -> None:
        """Rollback multiple migrations.
        
        Args:
            migrations: List of available migrations
            count: Number of migrations to rollback
        """
        applied = self.get_applied_migrations()
        
        if not applied:
            print("No migrations to rollback")
            return
        
        # Get migrations to rollback (most recent first)
        to_rollback = applied[-count:]
        migration_dict = {m.name: m for m in migrations}
        
        for name in reversed(to_rollback):
            if name in migration_dict:
                self.rollback_migration(migration_dict[name])
            else:
                print(f"Warning: Migration {name} not found in available migrations")
    
    def _sort_by_dependencies(self, migrations: List[Migration]) -> List[Migration]:
        """Sort migrations by dependencies.
        
        Args:
            migrations: List of migrations to sort
            
        Returns:
            Sorted list of migrations
        """
        sorted_migrations = []
        remaining = migrations.copy()
        applied = set(self.get_applied_migrations())
        
        while remaining:
            # Find migrations with satisfied dependencies
            ready = []
            for migration in remaining:
                deps_satisfied = all(
                    dep in applied or 
                    any(m.name == dep for m in sorted_migrations)
                    for dep in migration.dependencies
                )
                if deps_satisfied:
                    ready.append(migration)
            
            if not ready:
                # Circular dependency or missing dependency
                remaining_names = [m.name for m in remaining]
                raise ValueError(f"Circular or missing dependencies in migrations: {remaining_names}")
            
            # Add ready migrations
            for migration in ready:
                sorted_migrations.append(migration)
                remaining.remove(migration)
        
        return sorted_migrations
    
    def create_migration_file(self, name: str, operations: List[Operation], 
                            dependencies: Optional[List[str]] = None) -> str:
        """Create a migration file.
        
        Args:
            name: Migration name
            operations: List of operations
            dependencies: List of dependencies
            
        Returns:
            Path to created migration file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.py"
        filepath = self.migrations_dir / filename
        
        migration = Migration(name, operations, dependencies)
        
        # Generate migration file content
        content = f'''"""Migration: {name}

Created: {migration.timestamp}
Hash: {migration.hash}
"""

from ORM.migrations.operations import *
from ORM.migrations.migration import Migration

# Migration operations
operations = [
    # Add your operations here
    # Example:
    # CreateTable("users", {{
    #     "id": IntegerField(primary_key=True),
    #     "name": TextField(nullable=False),
    #     "email": TextField(unique=True)
    # }})
]

# Dependencies (list of migration names this depends on)
dependencies = {migration.dependencies}

# Create migration instance
migration = Migration("{name}", operations, dependencies)
'''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Created migration file: {filepath}")
        return str(filepath)
    
    def load_migrations_from_directory(self) -> List[Migration]:
        """Load all migrations from the migrations directory.
        
        Returns:
            List of loaded migrations
        """
        migrations = []
        
        for file_path in self.migrations_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            
            try:
                # Import migration module
                spec = importlib.util.spec_from_file_location("migration", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, 'migration'):
                    migrations.append(module.migration)
                
            except Exception as e:
                print(f"Failed to load migration {file_path}: {e}")
        
        return migrations