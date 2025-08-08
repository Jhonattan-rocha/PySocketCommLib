# Development Guide

This guide provides information for developers who want to contribute to PySocketCommLib or understand its internal architecture.

## Table of Contents

- [Project Structure](#project-structure)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
- [Testing](#testing)
- [Code Style](#code-style)
- [Contributing](#contributing)
- [Release Process](#release-process)

## Project Structure

```
PySocketCommLib/
├── PySocketCommLib/           # Main package
│   ├── __init__.py           # Package initialization
│   ├── config.py             # Configuration management
│   ├── cli.py                # Command-line interface
│   ├── Server/               # Server implementations
│   │   ├── __init__.py
│   │   ├── asyncserv/        # Async server
│   │   │   ├── __init__.py
│   │   │   ├── server.py     # Main async server
│   │   │   └── helpers/      # Helper modules
│   │   │       ├── __init__.py
│   │   │       └── rate_limiter.py
│   │   ├── threadserv/       # Threading server
│   │   │   ├── __init__.py
│   │   │   └── server.py
│   │   └── server_ops.py     # Server operations
│   ├── Client/               # Client implementations
│   │   ├── __init__.py
│   │   ├── asyncclient/      # Async client
│   │   │   ├── __init__.py
│   │   │   └── client.py
│   │   └── threadclient/     # Threading client
│   │       ├── __init__.py
│   │       └── client.py
│   ├── Connection/           # Connection types
│   │   ├── __init__.py
│   │   ├── websocket.py      # WebSocket connection
│   │   ├── http.py           # HTTP connection
│   │   └── tcp.py            # TCP connection
│   ├── Auth/                 # Authentication
│   │   ├── __init__.py
│   │   ├── auth.py           # Base auth classes
│   │   ├── basic.py          # Basic authentication
│   │   ├── token.py          # Token authentication
│   │   └── oauth.py          # OAuth authentication
│   ├── Crypto/               # Cryptography
│   │   ├── __init__.py
│   │   ├── encryption.py     # Encryption utilities
│   │   └── hashing.py        # Hashing utilities
│   ├── ORM/                  # Object-Relational Mapping
│   │   ├── __init__.py
│   │   ├── models.py         # Base model classes
│   │   ├── fields.py         # Field types
│   │   ├── connection.py     # Database connections
│   │   └── migrations/       # Database migrations
│   │       ├── __init__.py
│   │       ├── migration.py  # Migration management
│   │       └── operations.py # Migration operations
│   ├── Events/               # Event system
│   │   ├── __init__.py
│   │   ├── emitter.py        # Event emitter
│   │   └── handlers.py       # Event handlers
│   └── Tasks/                # Task management
│       ├── __init__.py
│       ├── scheduler.py      # Task scheduler
│       └── worker.py         # Task worker
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── test_server.py        # Server tests
│   ├── test_client.py        # Client tests
│   ├── test_orm.py           # ORM tests
│   ├── test_auth.py          # Authentication tests
│   ├── test_crypto.py        # Cryptography tests
│   └── test_config.json      # Test configuration
├── examples/                 # Example applications
│   ├── complete_example.py   # Comprehensive example
│   └── simple_client.py      # Simple client example
├── docs/                     # Documentation
├── setup.py                  # Package setup
├── requirements.txt          # Dependencies
├── README.md                 # Project overview
├── DEVELOPMENT.md            # This file
└── LICENSE                   # License file
```

## Development Setup

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/PySocketCommLib.git
   cd PySocketCommLib
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   
   # For development dependencies
   pip install -e .[dev]
   ```

4. **Install the package in development mode:**
   ```bash
   pip install -e .
   ```

### Current Status (Latest Improvements)

✅ **Completed Enhancements:**

1. **Configuration System Enhanced**
   - Improved error handling and validation
   - Better environment variable support
   - Enhanced logging configuration
   - Nested configuration support

2. **ORM System Improvements**
   - Enhanced field types with better validation
   - Improved query building capabilities
   - Better connection management
   - Enhanced migration system

3. **Server Functionality Enhanced**
   - Improved async server implementation
   - Better error handling and logging
   - Enhanced connection management
   - Rate limiting capabilities

4. **Import System Analysis and Fixes**
   - Comprehensive import analysis with `import_analyzer.py`
   - Systematic import conflict resolution with `fix_imports.py`
   - CLI modernization with local import support
   - Backup system for safe modifications

5. **Legacy Test Modernization**
   - Automated test updating with `test_updater.py`
   - 12 legacy tests modernized with proper imports
   - Unified test runner created
   - Backup system for original test files

6. **Comprehensive Testing and Validation**
   - Updated test suite with better coverage
   - Validation scripts for core components
   - Import conflict detection and resolution
   - Automated test modernization

7. **Examples and Documentation**
   - Practical usage examples
   - Comprehensive documentation
   - Setup and configuration guides
   - Best practices documentation

⚠️ **Known Limitations (Updated):**

1. **Remaining Import Conflicts**
   - Deep relative imports still cause issues (e.g., `...Abstracts.Auth`)
   - Some modules still use problematic import patterns
   - Package structure conflicts with local execution

2. **CLI Execution Issues**
   - CLI still has import resolution problems
   - Requires package installation or complex path manipulation
   - Local execution conflicts with relative imports

3. **Test Execution Challenges**
   - Modernized tests still fail due to import issues
   - Module resolution problems in test environment
   - Some legacy patterns persist in core modules

4. **Module Structure Conflicts**
   - Mix of relative and absolute imports creates inconsistency
   - Some modules expect package installation
   - Local development vs. installed package conflicts

🔄 **Next Steps Recommended (Updated):**

1. **Deep Import Resolution**
   - Fix remaining relative imports in core modules
   - Standardize all imports to work locally
   - Create consistent import patterns

2. **CLI Reconstruction**
   - Rebuild CLI with proper local imports
   - Implement robust path resolution
   - Test CLI functionality thoroughly

3. **Module Structure Optimization**
   - Consider flattening some nested imports
   - Simplify module dependencies
   - Ensure local execution compatibility

4. **Test Environment Setup**
   - Create proper test environment configuration
   - Fix remaining test import issues
   - Validate all test functionality

5. **Package Development Mode**
   - Consider implementing development mode installation
   - Create setup.py with proper dependencies
   - Enable editable installation for development

**Tools Created for Maintenance:**
- **`import_analyzer.py`**: Analyzes and reports import conflicts
- **`fix_imports.py`**: Systematically fixes import issues
- **`fix_imports_v2.py`**: Advanced import resolution
- **`test_updater.py`**: Modernizes legacy tests
- **`final_validation.py`**: Validates core component functionality
- **`demo_improvements.py`**: Demonstrates implemented features

### Development Dependencies

The following packages are recommended for development:

- `pytest` - Testing framework
- `pytest-asyncio` - Async testing support
- `pytest-cov` - Coverage reporting
- `black` - Code formatting
- `flake8` - Linting
- `mypy` - Type checking
- `sphinx` - Documentation generation

## Architecture Overview

### Design Principles

1. **Modularity**: Each component is designed to be independent and reusable
2. **Async-First**: Primary focus on asynchronous programming with threading support
3. **Type Safety**: Extensive use of type hints for better code quality
4. **Configuration-Driven**: Flexible configuration system for different environments
5. **Extensibility**: Plugin-like architecture for easy extension

### Core Patterns

- **Factory Pattern**: Used for creating server and client instances
- **Observer Pattern**: Event system for decoupled communication
- **Strategy Pattern**: Authentication and encryption implementations
- **Builder Pattern**: Configuration and connection setup
- **Repository Pattern**: ORM data access layer

## Core Components

### Server Architecture

#### AsyncServer
- **Purpose**: High-performance asynchronous server
- **Key Features**:
  - WebSocket and HTTP support
  - SSL/TLS encryption
  - Rate limiting
  - Authentication integration
  - Event-driven architecture

#### ThreadServer
- **Purpose**: Traditional threading-based server
- **Key Features**:
  - Simpler programming model
  - Good for CPU-bound tasks
  - Compatible with synchronous libraries

### Authentication System

#### Base Classes
- `BaseAuth`: Abstract authentication interface
- `AuthResult`: Authentication result container

#### Implementations
- `BasicAuth`: Username/password authentication
- `TokenAuth`: JWT and API token authentication
- `OAuthAuth`: OAuth 2.0 authentication
- `NoAuth`: No authentication (development/testing)

### ORM System

#### Core Components
- `BaseModel`: Base class for all models
- `Field`: Base field class with validation
- `Connection`: Database connection management
- `Migration`: Database schema management

#### Field Types
- `IntegerField`: Integer values
- `TextField`: Text/string values
- `BooleanField`: Boolean values
- `DateTimeField`: Date and time values
- `ForeignKey`: Relationships between models

### Event System

#### Components
- `EventEmitter`: Central event dispatcher
- `EventHandler`: Base class for event handlers
- `AsyncEventHandler`: Async event handler

#### Built-in Events
- `client_connected`: New client connection
- `client_disconnected`: Client disconnection
- `message_received`: Incoming message
- `authentication_success`: Successful authentication
- `authentication_failed`: Failed authentication

### Configuration System

#### Features
- Environment variable support
- JSON/YAML configuration files
- Runtime configuration updates
- Validation and type checking
- Default value management

## Testing

### Test Structure

Tests are organized by component:
- `test_server.py`: Server functionality
- `test_client.py`: Client functionality
- `test_orm.py`: ORM operations
- `test_auth.py`: Authentication
- `test_crypto.py`: Cryptography

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=PySocketCommLib

# Run specific test file
pytest tests/test_server.py

# Run with verbose output
pytest -v

# Run async tests
pytest -v tests/test_server.py::TestAsyncServer
```

### Test Configuration

Use `tests/test_config.json` for test-specific configuration:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8080,
    "max_connections": 100
  },
  "database": {
    "url": "sqlite:///:memory:"
  }
}
```

### Mocking

Use mocks for external dependencies:

```python
from unittest.mock import Mock, AsyncMock

# Mock database connection
mock_connection = Mock()
mock_connection.execute = AsyncMock(return_value=[])
```

## Code Style

### Formatting

Use `black` for code formatting:

```bash
# Format all files
black .

# Check formatting
black --check .
```

### Linting

Use `flake8` for linting:

```bash
# Run linter
flake8 PySocketCommLib/

# With specific configuration
flake8 --max-line-length=88 --extend-ignore=E203,W503 PySocketCommLib/
```

### Type Checking

Use `mypy` for type checking:

```bash
# Check types
mypy PySocketCommLib/

# With strict mode
mypy --strict PySocketCommLib/
```

### Style Guidelines

1. **Line Length**: Maximum 88 characters (Black default)
2. **Imports**: Use absolute imports, group by standard/third-party/local
3. **Docstrings**: Use Google-style docstrings
4. **Type Hints**: Required for all public functions and methods
5. **Variable Names**: Use descriptive names, avoid abbreviations

### Example Code Style

```python
from typing import Optional, Dict, Any
import asyncio
import logging

from ..auth import BaseAuth
from ..config import Config


class ExampleServer:
    """Example server implementation.
    
    This class demonstrates the coding style and patterns
    used throughout the PySocketCommLib project.
    
    Args:
        config: Server configuration
        auth: Authentication handler
        
    Attributes:
        is_running: Whether the server is currently running
        client_count: Number of connected clients
    """
    
    def __init__(self, config: Config, auth: Optional[BaseAuth] = None):
        self.config = config
        self.auth = auth
        self.is_running = False
        self.client_count = 0
        self._logger = logging.getLogger(__name__)
    
    async def start(self) -> None:
        """Start the server.
        
        Raises:
            RuntimeError: If server is already running
        """
        if self.is_running:
            raise RuntimeError("Server is already running")
        
        self._logger.info("Starting server...")
        self.is_running = True
    
    async def handle_client(self, client_data: Dict[str, Any]) -> bool:
        """Handle client connection.
        
        Args:
            client_data: Client connection information
            
        Returns:
            True if client was handled successfully
        """
        try:
            # Process client
            self.client_count += 1
            return True
        except Exception as e:
            self._logger.error(f"Error handling client: {e}")
            return False
```

## Contributing

### Workflow

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-feature`
3. **Make changes** following the code style guidelines
4. **Add tests** for new functionality
5. **Run tests**: `pytest`
6. **Update documentation** if needed
7. **Commit changes**: `git commit -m "Add new feature"`
8. **Push to fork**: `git push origin feature/new-feature`
9. **Create pull request**

### Pull Request Guidelines

- **Title**: Clear, descriptive title
- **Description**: Explain what changes were made and why
- **Tests**: Include tests for new functionality
- **Documentation**: Update docs if API changes
- **Backwards Compatibility**: Maintain compatibility when possible

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks

Examples:
```
feat(server): add WebSocket compression support
fix(orm): resolve connection pool leak
docs(readme): update installation instructions
```

## Release Process

### Version Numbering

Use semantic versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

### Release Steps

1. **Update version** in `setup.py` and `__init__.py`
2. **Update CHANGELOG.md** with release notes
3. **Run full test suite**: `pytest`
4. **Build package**: `python setup.py sdist bdist_wheel`
5. **Test package**: Install and test in clean environment
6. **Create git tag**: `git tag v1.0.0`
7. **Push changes**: `git push origin main --tags`
8. **Upload to PyPI**: `twine upload dist/*`
9. **Create GitHub release** with release notes

### Pre-release Checklist

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Version numbers are updated
- [ ] CHANGELOG.md is updated
- [ ] No breaking changes without major version bump
- [ ] Examples work with new version
- [ ] Performance benchmarks are acceptable

## Debugging

### Logging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

1. **Connection Issues**:
   - Check firewall settings
   - Verify port availability
   - Test with telnet/netcat

2. **SSL/TLS Issues**:
   - Verify certificate validity
   - Check certificate chain
   - Test with openssl s_client

3. **Performance Issues**:
   - Use profiling tools (cProfile, py-spy)
   - Monitor memory usage
   - Check for blocking operations in async code

4. **Database Issues**:
   - Check connection strings
   - Verify database permissions
   - Monitor connection pool usage

### Development Tools

- **IDE**: VS Code, PyCharm, or similar with Python support
- **Debugger**: Built-in Python debugger or IDE debugger
- **Profiler**: cProfile, py-spy, or memory_profiler
- **Network Tools**: Wireshark, tcpdump, netstat
- **Database Tools**: Database-specific clients and monitoring tools

---

For more information, see the main [README.md](README.md) or contact the maintainers.