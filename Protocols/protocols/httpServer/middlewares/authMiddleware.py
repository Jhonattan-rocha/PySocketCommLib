"""
AuthMiddleware — middleware ASGI de autenticação baseado em HttpAuth.

Uso:
    from PySocketCommLib.Auth import SimpleTokenHttpAuth
    from PySocketCommLib.Protocols import AuthMiddleware, MiddlewareController

    auth = SimpleTokenHttpAuth(token="meu-token-secreto")
    server = AsyncHttpServerProtocol(...)
    wrapped = MiddlewareController(server, [
        AuthMiddleware(auth, excluded_paths=["/health", "/ping"]),
    ])

Rotas listadas em excluded_paths passam sem validação (útil para health checks
e rotas públicas).

WebSocket e lifespan são sempre repassados sem validação — a autenticação WS
deve ser feita dentro do handler de WebSocket.
"""
from typing import Callable, List, Optional
from .....Auth.HttpAuth import HttpAuth


class AuthMiddleware:
    """
    Middleware que intercepta requisições HTTP e valida via HttpAuth.

    Se a validação falhar, responde com 401 e o corpo retornado por
    auth.unauthorized_message() sem chamar o próximo middleware.
    """

    def __init__(self, auth: HttpAuth, excluded_paths: Optional[List[str]] = None) -> None:
        self.auth = auth
        self.excluded_paths: set = set(excluded_paths or [])

    async def __call__(self, scope: dict, receive: Callable, send: Callable, next_middleware: Callable):
        # Só aplica autenticação em requisições HTTP
        if scope.get("type") != "http":
            await next_middleware(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if not path:
            raw = scope.get("raw_path", b"/")
            path = raw.decode("utf-8") if isinstance(raw, bytes) else raw

        if path in self.excluded_paths:
            await next_middleware(scope, receive, send)
            return

        headers: dict = {
            k.decode("utf-8").lower(): v.decode("utf-8")
            for k, v in scope.get("headers", [])
        }

        if not self.auth.validate_http(scope, headers):
            body = self.auth.unauthorized_message()
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await next_middleware(scope, receive, send)
