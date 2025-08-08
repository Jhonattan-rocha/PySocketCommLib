"""Database migration operations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..abstracts.field_types import BaseField


class Operation(ABC):
    """Base class for migration operations."""
    
    @abstractmethod
    def get_sql(self, dialect: str) -> str:
        """Generate SQL for this operation.
        
        Args:
            dialect: Database dialect (mysql, postgresql, sqlite)
            
        Returns:
            SQL statement string
        """
        pass
    
    @abstractmethod
    def get_reverse_operation(self) -> 'Operation':
        """Get the reverse operation for rollback.
        
        Returns:
            Reverse operation instance
        """
        pass


class CreateTable(Operation):
    """Create table operation."""
    
    def __init__(self, table_name: str, fields: Dict[str, BaseField]):
        """Initialize create table operation.
        
        Args:
            table_name: Name of the table to create
            fields: Dictionary of field name to field instance
        """
        self.table_name = table_name
        self.fields = fields
    
    def get_sql(self, dialect: str) -> str:
        """Generate CREATE TABLE SQL.
        
        Args:
            dialect: Database dialect
            
        Returns:
            CREATE TABLE SQL statement
        """
        field_definitions = []
        
        for field_name, field in self.fields.items():
            field_sql = f"{field_name} {field.get_sql_type(dialect)}"
            
            if field.primary_key:
                field_sql += " PRIMARY KEY"
            if not field.nullable:
                field_sql += " NOT NULL"
            if field.unique:
                field_sql += " UNIQUE"
            if field.default is not None:
                if isinstance(field.default, str):
                    field_sql += f" DEFAULT '{field.default}'"
                else:
                    field_sql += f" DEFAULT {field.default}"
            
            field_definitions.append(field_sql)
        
        fields_sql = ", ".join(field_definitions)
        return f"CREATE TABLE {self.table_name} ({fields_sql})"
    
    def get_reverse_operation(self) -> 'DropTable':
        """Get reverse operation (DROP TABLE).
        
        Returns:
            DropTable operation
        """
        return DropTable(self.table_name)


class DropTable(Operation):
    """Drop table operation."""
    
    def __init__(self, table_name: str, fields: Optional[Dict[str, BaseField]] = None):
        """Initialize drop table operation.
        
        Args:
            table_name: Name of the table to drop
            fields: Optional fields for reverse operation
        """
        self.table_name = table_name
        self.fields = fields or {}
    
    def get_sql(self, dialect: str) -> str:
        """Generate DROP TABLE SQL.
        
        Args:
            dialect: Database dialect
            
        Returns:
            DROP TABLE SQL statement
        """
        return f"DROP TABLE {self.table_name}"
    
    def get_reverse_operation(self) -> CreateTable:
        """Get reverse operation (CREATE TABLE).
        
        Returns:
            CreateTable operation
        """
        if not self.fields:
            raise ValueError("Cannot reverse DROP TABLE without field definitions")
        return CreateTable(self.table_name, self.fields)


class AddColumn(Operation):
    """Add column operation."""
    
    def __init__(self, table_name: str, column_name: str, field: BaseField):
        """Initialize add column operation.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column to add
            field: Field definition
        """
        self.table_name = table_name
        self.column_name = column_name
        self.field = field
    
    def get_sql(self, dialect: str) -> str:
        """Generate ADD COLUMN SQL.
        
        Args:
            dialect: Database dialect
            
        Returns:
            ALTER TABLE ADD COLUMN SQL statement
        """
        field_sql = f"{self.column_name} {self.field.get_sql_type(dialect)}"
        
        if not self.field.nullable:
            field_sql += " NOT NULL"
        if self.field.unique:
            field_sql += " UNIQUE"
        if self.field.default is not None:
            if isinstance(self.field.default, str):
                field_sql += f" DEFAULT '{self.field.default}'"
            else:
                field_sql += f" DEFAULT {self.field.default}"
        
        return f"ALTER TABLE {self.table_name} ADD COLUMN {field_sql}"
    
    def get_reverse_operation(self) -> 'DropColumn':
        """Get reverse operation (DROP COLUMN).
        
        Returns:
            DropColumn operation
        """
        return DropColumn(self.table_name, self.column_name, self.field)


class DropColumn(Operation):
    """Drop column operation."""
    
    def __init__(self, table_name: str, column_name: str, field: Optional[BaseField] = None):
        """Initialize drop column operation.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column to drop
            field: Optional field definition for reverse operation
        """
        self.table_name = table_name
        self.column_name = column_name
        self.field = field
    
    def get_sql(self, dialect: str) -> str:
        """Generate DROP COLUMN SQL.
        
        Args:
            dialect: Database dialect
            
        Returns:
            ALTER TABLE DROP COLUMN SQL statement
        """
        return f"ALTER TABLE {self.table_name} DROP COLUMN {self.column_name}"
    
    def get_reverse_operation(self) -> AddColumn:
        """Get reverse operation (ADD COLUMN).
        
        Returns:
            AddColumn operation
        """
        if not self.field:
            raise ValueError("Cannot reverse DROP COLUMN without field definition")
        return AddColumn(self.table_name, self.column_name, self.field)


class AlterColumn(Operation):
    """Alter column operation."""
    
    def __init__(self, table_name: str, column_name: str, 
                 old_field: BaseField, new_field: BaseField):
        """Initialize alter column operation.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column to alter
            old_field: Current field definition
            new_field: New field definition
        """
        self.table_name = table_name
        self.column_name = column_name
        self.old_field = old_field
        self.new_field = new_field
    
    def get_sql(self, dialect: str) -> str:
        """Generate ALTER COLUMN SQL.
        
        Args:
            dialect: Database dialect
            
        Returns:
            ALTER TABLE ALTER COLUMN SQL statement
        """
        field_sql = f"{self.column_name} {self.new_field.get_sql_type(dialect)}"
        
        if not self.new_field.nullable:
            field_sql += " NOT NULL"
        if self.new_field.unique:
            field_sql += " UNIQUE"
        if self.new_field.default is not None:
            if isinstance(self.new_field.default, str):
                field_sql += f" DEFAULT '{self.new_field.default}'"
            else:
                field_sql += f" DEFAULT {self.new_field.default}"
        
        if dialect.lower() == 'postgresql':
            return f"ALTER TABLE {self.table_name} ALTER COLUMN {field_sql}"
        elif dialect.lower() == 'mysql':
            return f"ALTER TABLE {self.table_name} MODIFY COLUMN {field_sql}"
        else:  # SQLite
            # SQLite doesn't support ALTER COLUMN directly
            return f"-- SQLite ALTER COLUMN not supported: {self.table_name}.{self.column_name}"
    
    def get_reverse_operation(self) -> 'AlterColumn':
        """Get reverse operation.
        
        Returns:
            AlterColumn operation with old and new fields swapped
        """
        return AlterColumn(self.table_name, self.column_name, 
                          self.new_field, self.old_field)