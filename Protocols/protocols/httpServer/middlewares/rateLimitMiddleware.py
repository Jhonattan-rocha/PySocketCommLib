import time
from collections import defaultdict
from ..Responses.Response import Response

class RateLimiterMiddleware:
    def __init__(self, limit=10, interval=60):
        self.limit = limit
        self.interval = interval
        self.requests = defaultdict(list)

    async def __call__(self, scope, receive, next_middleware):
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        current_time = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > current_time - self.interval]

        if len(self.requests[client_ip]) >= self.limit:
            response = Response(status=429, body=b"Too many requests")
            return response

        self.requests[client_ip].append(current_time)
        await next_middleware()  # Só continua se a requisição não for bloqueada
