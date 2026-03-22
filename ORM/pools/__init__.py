from queue import Queue, Empty
import asyncio
from ..abstracts.connection_types import Connection
from typing import Type


class ConnectionPool:
    """Pool de conexões síncrono com suporte a context manager."""

    def __init__(self, connection_class: Type[Connection], min_conn: int = 1, max_conn: int = 10, **conn_kwargs):
        self.pool: Queue[Connection] = Queue(maxsize=max(max_conn, min_conn))
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._initialized = False

    def initialize_pool(self):
        if self._initialized:
            return
        for _ in range(self._min_conn):
            conn = self._create_connection()
            self.pool.put(conn)
        self._initialized = True

    def _create_connection(self) -> Connection:
        conn = self.connection_class(**self.conn_kwargs)
        if not conn.connect():
            raise ConnectionError(
                f"Falha ao criar conexão no pool usando {self.connection_class.__name__}"
            )
        return conn

    def get_connection(self) -> Connection:
        if not self._initialized:
            self.initialize_pool()
        return self.pool.get()

    def release_connection(self, conn: Connection):
        if conn and getattr(conn, 'socket_connection', None) or getattr(conn, 'connection', None):
            self.pool.put(conn)
        else:
            # Conexão inválida — cria uma nova para manter o pool
            try:
                new_conn = self._create_connection()
                self.pool.put(new_conn)
            except Exception:
                pass  # Se não conseguir reconectar, o pool encolhe

    def __enter__(self) -> Connection:
        self._current_conn = self.get_connection()
        return self._current_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_connection(self._current_conn)
        self._current_conn = None


class AsyncConnectionPool:
    """Pool de conexões assíncrono com suporte a context manager."""

    def __init__(self, connection_class: Type[Connection], min_conn: int = 1, max_conn: int = 10, **conn_kwargs):
        self.pool: asyncio.Queue[Connection] = asyncio.Queue(maxsize=max(max_conn, min_conn))
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

    async def _create_connection(self) -> Connection:
        conn = self.connection_class(**self.conn_kwargs)
        if not await conn.connect():
            raise ConnectionError(
                f"Falha ao criar conexão async no pool usando {self.connection_class.__name__}"
            )
        return conn

    async def get_connection(self) -> Connection:
        if not self._initialized:
            await self.initialize_pool()
        return await self.pool.get()

    async def release_connection(self, conn: Connection):
        if conn and (getattr(conn, 'socket_connection', None) or getattr(conn, 'connection', None)):
            await self.pool.put(conn)
        else:
            try:
                new_conn = await self._create_connection()
                await self.pool.put(new_conn)
            except Exception:
                pass

    async def __aenter__(self) -> Connection:
        self._current_conn = await self.get_connection()
        return self._current_conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release_connection(self._current_conn)
        self._current_conn = None
