"""
HttpAuth — extensão de Auth para contextos HTTP.

O Auth base foi projetado para sockets (validate_token lê bytes do socket).
HttpAuth adiciona validate_http, que opera sobre os headers ASGI, permitindo
que a mesma hierarquia de autenticação funcione tanto em servidores socket
quanto em servidores HTTP.
"""
from abc import abstractmethod
from typing import Dict
from ..Abstracts.Auth import Auth


class HttpAuth(Auth):
    """
    Classe base para autenticação em contextos HTTP/ASGI.

    Subclasses devem implementar:
        validate_http  — decide se a requisição é autorizada
        unauthorized_message — corpo da resposta 401
    """

    def __init__(self, token: str = "") -> None:
        super().__init__(token)

    @abstractmethod
    def validate_http(self, scope: dict, headers: Dict[str, str]) -> bool:
        """
        Valida a requisição HTTP.

        Args:
            scope   — ASGI scope dict da requisição.
            headers — headers como dict {str_lower: str} (já decodificados).

        Returns:
            True se autorizado, False caso contrário.
        """
        ...

    @abstractmethod
    def unauthorized_message(self) -> bytes:
        """Corpo da resposta 401 Unauthorized."""
        ...
