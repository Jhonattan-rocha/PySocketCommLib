import sqlite3
from typing import Any, List, Tuple, Optional

class SQLiteDriver:
    def __init__(self, db_path: str):
        """
        Inicializa o driver SQLite.
        :param db_path: Caminho do banco de dados SQLite.
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
    
    def connect(self):
        """Estabelece uma conexão com o banco de dados."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
    
    def disconnect(self):
        """Fecha a conexão com o banco de dados."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def begin(self):
        """Inicia uma transação."""
        if self.conn:
            self.conn.execute("BEGIN;")
    
    def commit(self):
        """Confirma a transação."""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Desfaz a transação."""
        if self.conn:
            self.conn.rollback()
    
    def run(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple]:
        """
        Executa uma query SQL e retorna os resultados (caso seja uma consulta).
        :param query: A string da query SQL.
        :param params: Parâmetros opcionais para a query.
        :return: Lista de tuplas contendo os resultados.
        """
        if self.cursor is None:
            raise ConnectionError("Não há conexão ativa com o banco de dados.")
        
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        
        if query.strip().upper().startswith("SELECT"):
            return self.cursor.fetchall()
        return []
    
    def execute_many(self, query: str, param_list: List[Tuple[Any, ...]]):
        """Executa múltiplas queries ao mesmo tempo."""
        if self.cursor is None:
            raise ConnectionError("Não há conexão ativa com o banco de dados.")
        self.cursor.executemany(query, param_list)
    
    def last_insert_id(self) -> int:
        """Retorna o último ID inserido."""
        if self.cursor:
            return self.cursor.lastrowid
        return -1

if __name__ == "__main__":
    driver = SQLiteDriver("test.db")
    driver.connect()
    driver.run("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    driver.run("INSERT INTO users (name) VALUES (?)", ("Alice",))
    driver.commit()
    result = driver.run("SELECT * FROM users")
    print(result)
    driver.disconnect()
