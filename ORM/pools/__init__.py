import asyncio
import threading
from queue import Queue, Empty
from typing import Type

from ..abstracts.connection_types import Connection


class ConnectionPool:
    """
    Pool de conexões síncrono com suporte a context manager.

    Uso básico::

        pool = ConnectionPool(SqliteConnection, min_conn=2, max_conn=10, database="db.sqlite3")
        pool.initialize_pool()

        with pool as conn:
            conn.run("SELECT 1")

        # ou explicitamente:
        conn = pool.get_connection()
        try:
            conn.run("SELECT 1")
        finally:
            pool.release_connection(conn)
    """

    def __init__(self, connection_class: Type[Connection],
                 min_conn: int = 1, max_conn: int = 10, **conn_kwargs):
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._max_conn = max_conn
        self._pool: Queue[Connection] = Queue(maxsize=max_conn)
        self._lock = threading.Lock()
        self._total = 0          # conexões criadas (abertas)
        self._initialized = False

    def initialize_pool(self) -> None:
        with self._lock:
            if self._initialized:
                return
            for _ in range(self._min_conn):
                conn = self._create_connection()
                self._pool.put(conn)
            self._initialized = True

    def _create_connection(self) -> Connection:
        conn = self.connection_class(**self.conn_kwargs)
        if not conn.connect():
            raise ConnectionError(
                f"Falha ao criar conexão no pool: {self.connection_class.__name__}"
            )
        self._total += 1
        return conn

    def _is_alive(self, conn: Connection) -> bool:
        """Verifica se a conexão ainda está ativa via atributo _conn da base."""
        return conn._conn is not None

    def get_connection(self, timeout: float = 30.0) -> Connection:
        """Retorna uma conexão do pool. Bloqueia até `timeout` segundos."""
        if not self._initialized:
            self.initialize_pool()
        try:
            return self._pool.get(timeout=timeout)
        except Empty:
            raise TimeoutError(
                f"Nenhuma conexão disponível no pool após {timeout}s "
                f"(max_conn={self._max_conn})."
            )

    def release_connection(self, conn: Connection) -> None:
        """Devolve a conexão ao pool. Se estiver morta, cria uma nova."""
        if conn is None:
            return
        if self._is_alive(conn):
            self._pool.put(conn)
        else:
            # Conexão morta — substitui para manter o pool saudável
            try:
                new_conn = self._create_connection()
                self._pool.put(new_conn)
            except Exception:
                with self._lock:
                    self._total -= 1  # pool encolheu

    def close_all(self) -> None:
        """Fecha todas as conexões do pool e reseta o estado."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.disconnect()
            except Empty:
                break
        with self._lock:
            self._total = 0
            self._initialized = False

    def __enter__(self) -> Connection:
        self._ctx_conn = self.get_connection()
        return self._ctx_conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release_connection(self._ctx_conn)
        self._ctx_conn = None


class AsyncConnectionPool:
    """
    Pool de conexões assíncrono com suporte a context manager.

    Uso básico::

        pool = AsyncConnectionPool(PsqlConnection, min_conn=2, max_conn=10,
                                   host="localhost", port=5432, ...)
        await pool.initialize_pool()

        async with pool as conn:
            await conn.run("SELECT 1")
    """

    def __init__(self, connection_class: Type[Connection],
                 min_conn: int = 1, max_conn: int = 10, **conn_kwargs):
        self.connection_class = connection_class
        self.conn_kwargs = conn_kwargs
        self._min_conn = min_conn
        self._max_conn = max_conn
        self._pool: asyncio.Queue[Connection] = asyncio.Queue(maxsize=max_conn)
        self._total = 0
        self._initialized = False

    async def initialize_pool(self) -> None:
        if self._initialized:
            return
        for _ in range(self._min_conn):
            conn = await self._create_connection()
            await self._pool.put(conn)
        self._initialized = True

    async def _create_connection(self) -> Connection:
        """Cria uma nova conexão em thread pool (connect() é síncrono)."""
        loop = asyncio.get_running_loop()
        conn = self.connection_class(**self.conn_kwargs)
        ok = await loop.run_in_executor(None, conn.connect)
        if not ok:
            raise ConnectionError(
                f"Falha ao criar conexão async no pool: {self.connection_class.__name__}"
            )
        self._total += 1
        return conn

    def _is_alive(self, conn: Connection) -> bool:
        return conn._conn is not None

    async def get_connection(self, timeout: float = 30.0) -> Connection:
        """Retorna uma conexão do pool. Aguarda até `timeout` segundos."""
        if not self._initialized:
            await self.initialize_pool()
        try:
            return await asyncio.wait_for(self._pool.get(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Nenhuma conexão disponível no pool após {timeout}s "
                f"(max_conn={self._max_conn})."
            )

    async def release_connection(self, conn: Connection) -> None:
        """Devolve a conexão ao pool. Se estiver morta, cria uma nova."""
        if conn is None:
            return
        if self._is_alive(conn):
            await self._pool.put(conn)
        else:
            try:
                new_conn = await self._create_connection()
                await self._pool.put(new_conn)
            except Exception:
                self._total -= 1

    async def close_all(self) -> None:
        """Fecha todas as conexões do pool e reseta o estado."""
        loop = asyncio.get_running_loop()
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                await loop.run_in_executor(None, conn.disconnect)
            except asyncio.QueueEmpty:
                break
        self._total = 0
        self._initialized = False

    async def __aenter__(self) -> Connection:
        self._ctx_conn = await self.get_connection()
        return self._ctx_conn

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release_connection(self._ctx_conn)
        self._ctx_conn = None
