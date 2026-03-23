"""
ConnectionContext — representação leve de uma conexão aceita pelo servidor.

Substitui o antipadrão de criar instâncias de Client dentro do Server
(dependência circular Server → Client). O servidor passa a gerenciar
contextos de conexão, que são simples contêineres de estado sem lógica
de negócio de cliente.
"""
import asyncio
import socket
import ssl
import uuid as _uuid_module
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass
class AsyncConnectionContext:
    """
    Contexto de uma conexão aceita por um AsyncServer.

    Atributos:
        reader   — StreamReader da conexão.
        writer   — StreamWriter da conexão.
        address  — Endereço remoto (host, port).
        uuid     — Identificador único gerado automaticamente.
        metadata — Dicionário livre para armazenar dados por conexão
                   (ex: rate-limit bucket, dados de auth, sessão, etc.).
    """
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    address: Tuple
    uuid: str = field(default_factory=lambda: str(_uuid_module.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_closing(self) -> bool:
        """Retorna True se o writer está sendo fechado."""
        return self.writer.is_closing()

    async def disconnect(self) -> None:
        """Fecha a conexão de forma segura."""
        try:
            if not self.writer.is_closing():
                self.writer.close()
                await self.writer.wait_closed()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"AsyncConnectionContext(uuid={self.uuid}, address={self.address})"


@dataclass
class ThreadConnectionContext:
    """
    Contexto de uma conexão aceita por um ThreadServer.

    Atributos:
        connection — Socket da conexão (raw ou SSL).
        address    — Endereço remoto (host, port).
        uuid       — Identificador único gerado automaticamente.
        metadata   — Dicionário livre para armazenar dados por conexão.
    """
    connection: Any  # socket.socket | ssl.SSLSocket
    address: Tuple
    uuid: str = field(default_factory=lambda: str(_uuid_module.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_closing(self) -> bool:
        """
        Tenta detectar se a conexão foi encerrada via MSG_PEEK não-bloqueante.
        Retorna True se parecer fechada, False se ainda ativa.
        """
        try:
            self.connection.setblocking(False)
            data = self.connection.recv(1, socket.MSG_PEEK)
            self.connection.setblocking(True)
            return len(data) == 0
        except BlockingIOError:
            # Nenhum dado disponível agora, mas conexão ainda aberta
            self.connection.setblocking(True)
            return False
        except (OSError, Exception):
            return True

    def disconnect(self) -> None:
        """Fecha a conexão de forma segura."""
        try:
            self.connection.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"ThreadConnectionContext(uuid={self.uuid}, address={self.address})"
