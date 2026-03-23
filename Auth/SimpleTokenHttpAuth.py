"""
SimpleTokenHttpAuth — autenticação HTTP via Bearer token no header Authorization.

Uso:
    auth = SimpleTokenHttpAuth(token="meu-token-secreto")

    server = AsyncHttpServerProtocol(...)
    wrapped = MiddlewareController(server, [AuthMiddleware(auth)])

O cliente deve enviar o header:
    Authorization: Bearer meu-token-secreto
"""
from typing import Dict
from .HttpAuth import HttpAuth


class SimpleTokenHttpAuth(HttpAuth):
    """
    Valida requisições HTTP comparando o token do header Authorization
    com o token esperado.

    Rotas públicas devem ser excluídas via excluded_paths no AuthMiddleware.
    """

    def __init__(self, token: str) -> None:
        super().__init__(token)

    def validate_http(self, scope: dict, headers: Dict[str, str]) -> bool:
        """Aceita Authorization: Bearer <token>."""
        auth_header = headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            received = auth_header[7:].strip()
            return received == self.token
        return False

    def unauthorized_message(self) -> bytes:
        return b'{"detail": "Unauthorized"}'

    # --- Implementações obrigatórias da base Auth (contexto socket) ---

    def get_token(self, client=None) -> str:
        return self.token

    def set_token(self, client=None, token: str = "") -> str:
        self.token = token

    def validate_token(self, client=None) -> bool:
        """Não aplicável em contexto HTTP — delega ao validate_http."""
        return True

    def generate_token(self) -> str:
        return self.generate_random_str(32)
