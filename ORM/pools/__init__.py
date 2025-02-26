from queue import Queue
import asyncio
from ..abstracts.connection_types import Connection

class ConnectionPool:
    def __init__(self, min_conn=1, max_conn=10):
        self.pool = Queue(maxsize=max(max_conn, min_conn))

    def init(self, host: str = "localhost", port: int = 8081, user: str = "", password: str = "", database: str = ""):
        for _ in range(self.pool.maxsize):
            conn = Connection(host, port, user, password, database)
            self.pool.put(conn)

    def get_connection(self):
        """Pega uma conexão do pool"""
        return self.pool.get()

    def release_connection(self, conn):
        """Devolve conexão ao pool"""
        self.pool.put(conn)


class AsyncConnectionPool:
    def __init__(self, min_conn=1, max_conn=10):
        self.pool = asyncio.Queue(maxsize=max(max_conn, min_conn))

    async def init(self, host: str = "localhost", port: int = 8081, user: str = "", password: str = "", database: str = ""):
        for _ in range(self.pool.maxsize):
            conn = Connection(host, port, user, password, database)
            await self.pool.put(conn)

    async def get_connection(self):
        """Pega uma conexão do pool"""
        return await self.pool.get()

    async def release_connection(self, conn):
        """Devolve conexão ao pool"""
        await self.pool.put(conn)
