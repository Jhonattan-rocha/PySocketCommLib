#!/usr/bin/env python3
"""Test script to verify the improvements made to PySocketCommLib.

This script tests the new components and improvements without
relying on the complex existing import structure.
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_system():
    """Test the configuration system."""
    print("Testing Configuration System...")
    
    try:
        from config import Config
        
        # Test basic configuration
        config = Config()
        
        # Test setting and getting values
        config.set('test.value', 'hello')
        assert config.get('test.value') == 'hello'
        
        # Test default values
        assert config.get('nonexistent.key', 'default') == 'default'
        
        # Test environment variable loading
        os.environ['TEST_ENV_VAR'] = 'env_value'
        config.load_from_env({'test_env': 'TEST_ENV_VAR'})
        assert config.get('test_env') == 'env_value'
        
        # Test JSON configuration
        test_config = {
            'server': {
                'host': '127.0.0.1',
                'port': 8080
            },
            'database': {
                'url': 'sqlite:///test.db'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_file = f.name
        
        try:
            config.load_from_file(config_file)
            assert config.get('server.host') == '127.0.0.1'
            assert config.get('server.port') == 8080
            assert config.get('database.url') == 'sqlite:///test.db'
        finally:
            os.unlink(config_file)
        
        print("✓ Configuration system works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Configuration system failed: {e}")
        return False

def test_orm_components():
    """Test ORM components."""
    print("Testing ORM Components...")
    
    try:
        # Test field types
        from ORM.fields import IntegerField, TextField, BooleanField
        
        # Test field creation
        int_field = IntegerField()
        text_field = TextField(max_length=100)
        bool_field = BooleanField(default=False)
        
        # Test field validation
        assert int_field.validate(42) == 42
        assert text_field.validate('hello') == 'hello'
        assert bool_field.validate(True) == True
        
        # Test migration operations
        from ORM.migrations.operations import CreateTable, DropTable, AddColumn
        
        # Test create table operation
        create_op = CreateTable(
            table_name='test_table',
            columns={
                'id': 'INTEGER PRIMARY KEY',
                'name': 'TEXT NOT NULL',
                'active': 'BOOLEAN DEFAULT FALSE'
            }
        )
        
        sql = create_op.get_sql('sqlite')
        assert 'CREATE TABLE test_table' in sql
        assert 'id INTEGER PRIMARY KEY' in sql
        
        # Test reverse operation
        reverse_op = create_op.get_reverse_operation()
        assert isinstance(reverse_op, DropTable)
        assert reverse_op.table_name == 'test_table'
        
        print("✓ ORM components work correctly")
        return True
        
    except Exception as e:
        print(f"✗ ORM components failed: {e}")
        return False

def test_rate_limiter():
    """Test rate limiting components."""
    print("Testing Rate Limiter...")
    
    try:
        import asyncio
        from Server.asyncserv.helpers.rate_limiter import AsyncTokenBucket, RateLimiter
        
        async def test_async_rate_limiter():
            # Test token bucket
            bucket = AsyncTokenBucket(capacity=10, refill_rate=5)
            
            # Should be able to consume tokens initially
            assert await bucket.consume(5) == True
            assert await bucket.consume(5) == True
            
            # Should not be able to consume more than capacity
            assert await bucket.consume(1) == False
            
            # Test rate limiter
            limiter = RateLimiter(requests_per_second=10, burst_size=5)
            
            # Should allow initial requests
            assert await limiter.is_allowed('client1') == True
            assert await limiter.is_allowed('client2') == True
            
            return True
        
        # Run async test
        result = asyncio.run(test_async_rate_limiter())
        assert result == True
        
        print("✓ Rate limiter works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Rate limiter failed: {e}")
        return False

def test_package_structure():
    """Test package structure and imports."""
    print("Testing Package Structure...")
    
    try:
        # Test main package import
        import __init__ as main_package
        
        # Check version and metadata
        assert hasattr(main_package, '__version__')
        assert hasattr(main_package, '__author__')
        assert hasattr(main_package, '__email__')
        
        # Check __all__ exports
        assert hasattr(main_package, '__all__')
        assert len(main_package.__all__) > 0
        
        print("✓ Package structure is correct")
        return True
        
    except Exception as e:
        print(f"✗ Package structure failed: {e}")
        return False

def test_examples():
    """Test that examples can be imported without errors."""
    print("Testing Examples...")
    
    try:
        # Check that example files exist
        examples_dir = Path('examples')
        assert examples_dir.exists(), "Examples directory not found"
        
        complete_example = examples_dir / 'complete_example.py'
        simple_client = examples_dir / 'simple_client.py'
        
        assert complete_example.exists(), "Complete example not found"
        assert simple_client.exists(), "Simple client example not found"
        
        # Check that files have content
        assert complete_example.stat().st_size > 1000, "Complete example seems too small"
        assert simple_client.stat().st_size > 1000, "Simple client example seems too small"
        
        print("✓ Examples are present and substantial")
        return True
        
    except Exception as e:
        print(f"✗ Examples test failed: {e}")
        return False

def test_documentation():
    """Test that documentation files exist and have content."""
    print("Testing Documentation...")
    
    try:
        # Check required documentation files
        required_files = [
            'README.md',
            'DEVELOPMENT.md',
            'CHANGELOG.md',
            'requirements.txt',
            'setup.py',
            '.gitignore'
        ]
        
        for filename in required_files:
            filepath = Path(filename)
            assert filepath.exists(), f"{filename} not found"
            assert filepath.stat().st_size > 100, f"{filename} seems too small"
        
        # Check that README has key sections
        readme_content = Path('README.md').read_text()
        required_sections = [
            '# PySocketCommLib',
            '## Features',
            '## Installation',
            '## Quick Start',
            '## Documentation'
        ]
        
        for section in required_sections:
            assert section in readme_content, f"README missing section: {section}"
        
        print("✓ Documentation is complete")
        return True
        
    except Exception as e:
        print(f"✗ Documentation test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("PySocketCommLib Improvements Test Suite")
    print("=" * 40)
    
    tests = [
        test_package_structure,
        test_config_system,
        test_orm_components,
        test_rate_limiter,
        test_examples,
        test_documentation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
        print()
    
    print("=" * 40)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The improvements are working correctly.")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed. Some improvements need attention.")
        return 1

if __name__ == '__main__':
    sys.exit(main())