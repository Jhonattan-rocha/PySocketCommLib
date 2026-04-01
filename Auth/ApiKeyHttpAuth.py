"""
ApiKeyHttpAuth — autenticação HTTP via API Key em header customizado.

O cliente deve enviar o header configurado (padrão: ``X-API-Key``):
    X-API-Key: minha-chave-secreta

Uso:
    auth = ApiKeyHttpAuth(api_key="minha-chave-secreta")

    # Com header customizado:
    auth = ApiKeyHttpAuth(api_key="minha-chave", header_name="X-Auth-Token")
"""
import hmac
from typing import Dict

from .HttpAuth import HttpAuth


class ApiKeyHttpAuth(HttpAuth):
    """
    Valida requisições HTTP comparando a chave no header ``header_name``
    com a chave configurada.  A comparação é feita em tempo constante.

    Args:
        api_key:     Chave esperada.
        header_name: Nome do header HTTP (case-insensitive).
                     Padrão: ``x-api-key``.
    """

    def __init__(self, api_key: str, header_name: str = "x-api-key") -> None:
        super().__init__(token=api_key)
        self.api_key = api_key
        self.header_name = header_name.lower()

    def validate_http(self, scope: dict, headers: Dict[str, str]) -> bool:
        received = headers.get(self.header_name, "")
        if not received:
            return False
        return hmac.compare_digest(received.encode(), self.api_key.encode())

    def unauthorized_message(self) -> bytes:
        return b'{"detail": "Unauthorized"}'

    # --- Auth base socket stubs (not used in HTTP context) ---

    def get_token(self, client=None) -> str:
        return self.api_key

    def set_token(self, client=None, token: str = "") -> str:
        self.api_key = token
        self.token = token
        return token

    def validate_token(self, client=None) -> bool:
        return True

    def generate_token(self) -> str:
        return self.generate_random_str(32)
