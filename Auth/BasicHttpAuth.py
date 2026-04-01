"""
BasicHttpAuth — autenticação HTTP via Basic Auth (RFC 7617).

O cliente deve enviar o header:
    Authorization: Basic <base64(username:password)>

Uso:
    auth = BasicHttpAuth(username="admin", password="s3cr3t")
"""
import base64
from typing import Dict

from .HttpAuth import HttpAuth


class BasicHttpAuth(HttpAuth):
    """
    Valida requisições HTTP usando HTTP Basic Auth.

    Compara username e password recebidos no header ``Authorization: Basic``
    com as credenciais configuradas na instância.  A comparação é feita em
    tempo constante para evitar ataques de timing.
    """

    def __init__(self, username: str, password: str) -> None:
        super().__init__(token="")
        self.username = username
        self.password = password

    def validate_http(self, scope: dict, headers: Dict[str, str]) -> bool:
        auth_header = headers.get("authorization", "")
        if not auth_header.lower().startswith("basic "):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
            recv_user, _, recv_pass = decoded.partition(":")
        except Exception:
            return False
        return self._safe_compare(recv_user, self.username) and \
               self._safe_compare(recv_pass, self.password)

    @staticmethod
    def _safe_compare(a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        import hmac
        return hmac.compare_digest(a.encode(), b.encode())

    def unauthorized_message(self) -> bytes:
        return b'{"detail": "Unauthorized"}'

    # --- Auth base socket stubs (not used in HTTP context) ---

    def get_token(self, client=None) -> str:
        return ""

    def set_token(self, client=None, token: str = "") -> str:
        return token

    def validate_token(self, client=None) -> bool:
        return True

    def generate_token(self) -> str:
        return self.generate_random_str(32)
