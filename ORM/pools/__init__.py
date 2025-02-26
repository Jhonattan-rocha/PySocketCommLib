from queue import Queue
import asyncio
from ..abstracts.connection_types import Connection

class ConnectionPool:
    """Synchronous Connection Pool."""
    def __init__(self, connection_class, min_conn=1, max_conn=10, **conn_kwargs):
        self.pool = Queue(maxsize=max(max_conn, min_conn))
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._initialized = False

    def initialize_pool(self):
        if self._initialized:
            return # Avoid re-initialization
        for _ in range(self._min_conn):
            conn = self._create_connection()
            self.pool.put(conn)
        self._initialized = True

    def _create_connection(self):
        conn = self.connection_class(**self.conn_kwargs)
        conn.connect() # Establish connection when creating
        return conn

    def get_connection(self):
        """Picks a connection from the pool. Initializes pool on first call."""
        if not self._initialized:
            self.initialize_pool()
        return self.pool.get()

    def release_connection(self, conn):
        """Returns a connection back to the pool."""
        if conn and conn.connection: # Check if connection is valid before returning
            self.pool.put(conn)
        else:
            print("Warning: Releasing an invalid connection. Discarding it.")

class AsyncConnectionPool:
    """Asynchronous Connection Pool (Conceptual - needs async drivers for real async)."""
    def __init__(self, connection_class, min_conn=1, max_conn=10, **conn_kwargs):
        self.pool = asyncio.Queue(maxsize=max(max_conn, min_conn))
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

    async def _create_connection(self):
        conn = self.connection_class(**self.conn_kwargs)
        await conn.connect() # Assuming async connect method
        return conn

    async def get_connection(self):
        """Picks a connection from the pool. Initializes pool on first call."""
        if not self._initialized:
            await self.initialize_pool()
        return await self.pool.get()

    async def release_connection(self, conn):
        """Returns a connection back to the pool."""
        if conn and conn.connection: # Check if connection is valid before returning
            await self.pool.put(conn)
        else:
            print("Warning: Releasing an invalid connection. Discarding it.")
