from queue import Queue
import asyncio
from ..abstracts.connection_types import Connection
from typing import Type

class ConnectionPool:
    """Synchronous Connection Pool."""
    def __init__(self, connection_class: Type[Connection], min_conn=1, max_conn=10, **conn_kwargs): # Added type hint for connection_class
        self.pool: Queue[Connection] = Queue(maxsize=max(max_conn, min_conn)) # Added type hint for pool
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._initialized = False

    def initialize_pool(self):
        if self._initialized:
            return  # Avoid re-initialization
        for _ in range(self._min_conn):
            conn = self._create_connection()
            self.pool.put(conn)
        self._initialized = True

    def _create_connection(self) -> Connection:  # Added return type hint
        conn = self.connection_class(**self.conn_kwargs)
        if not conn.connect():  # Handle connection failure during pool creation
            raise ConnectionError(f"Failed to create connection for pool using {self.connection_class.__name__} and kwargs: {self.conn_kwargs}")
        return conn

    def get_connection(self) -> Connection:  # Added return type hint
        """Picks a connection from the pool. Initializes pool on first call."""
        if not self._initialized:
            self.initialize_pool()
        return self.pool.get()

    def release_connection(self, conn: Connection):  # Added type hint
        """Returns a connection back to the pool."""
        if conn and conn.connection:  # Check if connection is valid before returning
            self.pool.put(conn)
        else:
            print("Warning: Releasing an invalid connection. Discarding it.")
            # Consider logging error details here, maybe remove from pool count if implemented


class AsyncConnectionPool:
    """Asynchronous Connection Pool (Conceptual - needs async drivers for real async)."""
    def __init__(self, connection_class: Type[Connection], min_conn=1, max_conn=10, **conn_kwargs):  # Added type hint for connection_class
        self.pool: asyncio.Queue[Connection] = asyncio.Queue(maxsize=max(max_conn, min_conn))  # Added type hint for pool
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._initialized = False

    async def initialize_pool(self):
        if self._initialized:
            return
        for _ in range(self._min_conn):
            conn = await self._create_connection()
            await self.pool.put(conn)
        self._initialized = True

    async def _create_connection(self) -> Connection:  # Added return type hint
        conn = self.connection_class(**self.conn_kwargs)
        if not await conn.connect():  # Assuming async connect method and handling connection failure
            raise ConnectionError(f"Async connection failed for pool using {self.connection_class.__name__} and kwargs: {self.conn_kwargs}")
        return conn

    async def get_connection(self) -> Connection:  # Added return type hint
        """Picks a connection from the pool. Initializes pool on first call."""
        if not self._initialized:
            await self.initialize_pool()
        return await self.pool.get()

    async def release_connection(self, conn: Connection):  # Added type hint
        """Returns a connection back to the pool."""
        if conn and conn.connection:  # Check if connection is valid before returning
            await self.pool.put(conn)
        else:
            print("Warning: Releasing an invalid connection. Discarding it.")
            # Consider logging error details here and handling pool count if implemented
