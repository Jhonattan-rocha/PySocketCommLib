"""Unit tests for ORM functionality."""

import unittest
import tempfile
import os
from pathlib import Path

from ORM.abstracts.field_types import IntegerField, TextField, BooleanField
from ORM.models.model import BaseModel
from ORM.connections.connection_types import ConnectionType
from ORM.migrations.operations import CreateTable, DropTable, AddColumn
from ORM.migrations.migration import Migration, MigrationManager


class TestUser(BaseModel):
    """Test user model."""
    
    def __init__(self):
        super().__init__()
        self.fields = {
            'id': IntegerField(primary_key=True),
            'name': TextField(nullable=False),
            'email': TextField(unique=True),
            'active': BooleanField(default=True)
        }
        self.table_name = 'test_users'


class MockConnection(ConnectionType):
    """Mock database connection for testing."""
    
    def __init__(self):
        self.executed_queries = []
        self.results = []
    
    def execute(self, query, params=None):
        """Mock execute method."""
        self.executed_queries.append((query, params))
        return self.results.pop(0) if self.results else None
    
    def close(self):
        """Mock close method."""
        pass
    
    def set_result(self, result):
        """Set mock result for next query."""
        self.results.append(result)


class TestFieldTypes(unittest.TestCase):
    """Test field type implementations."""
    
    def test_integer_field_sql_type(self):
        """Test IntegerField SQL type generation."""
        field = IntegerField()
        self.assertEqual(field.get_sql_type('sqlite'), 'INTEGER')
        self.assertEqual(field.get_sql_type('mysql'), 'INT')
        self.assertEqual(field.get_sql_type('postgresql'), 'INTEGER')
    
    def test_text_field_sql_type(self):
        """Test TextField SQL type generation."""
        field = TextField()
        self.assertEqual(field.get_sql_type('sqlite'), 'TEXT')
        self.assertEqual(field.get_sql_type('mysql'), 'TEXT')
        self.assertEqual(field.get_sql_type('postgresql'), 'TEXT')
    
    def test_boolean_field_sql_type(self):
        """Test BooleanField SQL type generation."""
        field = BooleanField()
        self.assertEqual(field.get_sql_type('sqlite'), 'BOOLEAN')
        self.assertEqual(field.get_sql_type('mysql'), 'BOOLEAN')
        self.assertEqual(field.get_sql_type('postgresql'), 'BOOLEAN')
    
    def test_field_properties(self):
        """Test field property settings."""
        field = IntegerField(
            primary_key=True,
            nullable=False,
            unique=True,
            default=0,
            index=True
        )
        
        self.assertTrue(field.primary_key)
        self.assertFalse(field.nullable)
        self.assertTrue(field.unique)
        self.assertEqual(field.default, 0)
        self.assertTrue(field.index)


class TestBaseModel(unittest.TestCase):
    """Test BaseModel functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.model = TestUser()
        self.connection = MockConnection()
        self.model.set_connection(self.connection)
    
    def test_model_initialization(self):
        """Test model initialization."""
        self.assertEqual(self.model.table_name, 'test_users')
        self.assertIn('id', self.model.fields)
        self.assertIn('name', self.model.fields)
        self.assertIn('email', self.model.fields)
        self.assertIn('active', self.model.fields)
    
    def test_build_where_clause(self):
        """Test WHERE clause building."""
        # Test equality
        where_clause = self.model.build_where_clause('name', 'eq', 'John')
        self.assertEqual(where_clause, "name = 'John'")
        
        # Test less than
        where_clause = self.model.build_where_clause('id', 'lt', 10)
        self.assertEqual(where_clause, "id < 10")
        
        # Test LIKE
        where_clause = self.model.build_where_clause('email', 'like', '%@example.com')
        self.assertEqual(where_clause, "email LIKE '%@example.com'")
        
        # Test IN
        where_clause = self.model.build_where_clause('id', 'in', [1, 2, 3])
        self.assertEqual(where_clause, "id IN (1, 2, 3)")
    
    def test_generate_table_name(self):
        """Test table name generation."""
        # Test with explicit table name
        self.assertEqual(self.model.generate_table_name(), 'test_users')
        
        # Test with class name fallback
        model_without_table = BaseModel()
        expected_name = model_without_table.__class__.__name__.lower() + 's'
        self.assertEqual(model_without_table.generate_table_name(), expected_name)


class TestMigrationOperations(unittest.TestCase):
    """Test migration operations."""
    
    def test_create_table_operation(self):
        """Test CreateTable operation."""
        fields = {
            'id': IntegerField(primary_key=True),
            'name': TextField(nullable=False),
            'email': TextField(unique=True)
        }
        
        operation = CreateTable('users', fields)
        sql = operation.get_sql('sqlite')
        
        self.assertIn('CREATE TABLE users', sql)
        self.assertIn('id INTEGER PRIMARY KEY', sql)
        self.assertIn('name TEXT NOT NULL', sql)
        self.assertIn('email TEXT UNIQUE', sql)
    
    def test_drop_table_operation(self):
        """Test DropTable operation."""
        operation = DropTable('users')
        sql = operation.get_sql('sqlite')
        
        self.assertEqual(sql, 'DROP TABLE users')
    
    def test_add_column_operation(self):
        """Test AddColumn operation."""
        field = TextField(nullable=False, default='default_value')
        operation = AddColumn('users', 'description', field)
        sql = operation.get_sql('sqlite')
        
        self.assertIn('ALTER TABLE users ADD COLUMN', sql)
        self.assertIn('description TEXT NOT NULL', sql)
        self.assertIn("DEFAULT 'default_value'", sql)
    
    def test_operation_reversal(self):
        """Test operation reversal."""
        fields = {'id': IntegerField(primary_key=True)}
        create_op = CreateTable('users', fields)
        drop_op = create_op.get_reverse_operation()
        
        self.assertIsInstance(drop_op, DropTable)
        self.assertEqual(drop_op.table_name, 'users')


class TestMigrationManager(unittest.TestCase):
    """Test migration management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.connection = MockConnection()
        self.temp_dir = tempfile.mkdtemp()
        self.manager = MigrationManager(
            self.connection, 
            'sqlite', 
            self.temp_dir
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_migration_table_creation(self):
        """Test migration tracking table creation."""
        # Check that migration table creation SQL was executed
        executed_queries = [query[0] for query in self.connection.executed_queries]
        self.assertTrue(any('CREATE TABLE' in query and 'migrations' in query 
                          for query in executed_queries))
    
    def test_migration_application(self):
        """Test migration application."""
        # Create a simple migration
        operations = [CreateTable('test_table', {'id': IntegerField(primary_key=True)})]
        migration = Migration('create_test_table', operations)
        
        # Mock applied migrations query result
        self.connection.set_result([])  # No applied migrations
        
        # Apply migration
        self.manager.apply_migration(migration)
        
        # Check that CREATE TABLE and INSERT were executed
        executed_queries = [query[0] for query in self.connection.executed_queries]
        self.assertTrue(any('CREATE TABLE test_table' in query for query in executed_queries))
        self.assertTrue(any('INSERT INTO migrations' in query for query in executed_queries))
    
    def test_migration_file_creation(self):
        """Test migration file creation."""
        operations = [CreateTable('users', {'id': IntegerField(primary_key=True)})]
        
        filepath = self.manager.create_migration_file('create_users', operations)
        
        # Check that file was created
        self.assertTrue(os.path.exists(filepath))
        
        # Check file content
        with open(filepath, 'r') as f:
            content = f.read()
            self.assertIn('Migration: create_users', content)
            self.assertIn('operations = [', content)
    
    def test_dependency_sorting(self):
        """Test migration dependency sorting."""
        # Create migrations with dependencies
        migration1 = Migration('create_users', [], [])
        migration2 = Migration('create_posts', [], ['create_users'])
        migration3 = Migration('add_user_email', [], ['create_users'])
        
        migrations = [migration2, migration3, migration1]  # Unsorted order
        
        # Mock applied migrations
        self.connection.set_result([])  # No applied migrations
        
        sorted_migrations = self.manager._sort_by_dependencies(migrations)
        
        # Check that create_users comes first
        self.assertEqual(sorted_migrations[0].name, 'create_users')
        # Other two can be in any order since they don't depend on each other
        remaining_names = [m.name for m in sorted_migrations[1:]]
        self.assertIn('create_posts', remaining_names)
        self.assertIn('add_user_email', remaining_names)


if __name__ == '__main__':
    unittest.main()