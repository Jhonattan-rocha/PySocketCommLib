import time
from collections import defaultdict
from ..Responses.Response import Response

class RateLimiterMiddleware:
    def __init__(self, limit=10, interval=60, exempt_routes=None):
        self.limit = limit
        self.interval = interval
        self.requests = defaultdict(list)
        self.exempt_routes = exempt_routes or []  # Permitir exceções

    async def __call__(self, scope, receive, send, next_middleware):
        path = scope.get("path", "")

        # Permitir exceções para rotas específicas (como /health ou /status)
        if path in self.exempt_routes:
            await next_middleware(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        current_time = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > current_time - self.interval]

        if len(self.requests[client_ip]) >= self.limit:
            response = Response(status=429, body=b"Too many requests")
            await response.send_asgi(send)
            return

        self.requests[client_ip].append(current_time)
        await next_middleware(scope, receive, send)
