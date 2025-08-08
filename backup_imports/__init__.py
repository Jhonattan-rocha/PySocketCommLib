"""PySocketCommLib - A comprehensive Python library for low-level socket communication.

This library provides tools for creating socket-based systems including:
- WebSocket and HTTP servers
- ORM for database operations
- Authentication and encryption systems
- Async and threaded client/server implementations
"""

__version__ = "0.2.0"
__author__ = "Jhonattan Rocha"
__email__ = "jhonattan246rocha@gmail.com"

# Core components
from .Server import AsyncServer, ThreadServer
from .Client import AsyncClient, ThreadClient
from .Auth import NoAuth, SimpleTokenAuth
from .Crypt import Crypt
from .Events import Events
from .Files import File
from .Options import Server_ops, Client_ops, SSLContextOps
from .TaskManager import AsyncTaskManager, TaskManager

# ORM components
from .ORM import (
    BaseModel, BaseField, IntegerField, TextField, FloatField,
    BooleanField, DateTimeField, DecimalField, ForeignKeyField,
    JSONField, UUIDField, Select, Insert, Update, Delete
)

# Connection types
from .Connection_type import Types

__all__ = [
    # Core
    "AsyncServer", "ThreadServer", "AsyncClient", "ThreadClient",
    "NoAuth", "SimpleTokenAuth", "Crypt", "Events", "File",
    "Server_ops", "Client_ops", "SSLContextOps",
    "AsyncTaskManager", "TaskManager", "Types",
    
    # ORM
    "BaseModel", "BaseField", "IntegerField", "TextField", "FloatField",
    "BooleanField", "DateTimeField", "DecimalField", "ForeignKeyField",
    "JSONField", "UUIDField", "Select", "Insert", "Update", "Delete",
]