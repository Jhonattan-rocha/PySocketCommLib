from ..Responses.AsyncResponses.Response import Response
from collections import defaultdict
import time

class RateLimiterMiddleware:
    def __init__(self, app, limit=10, interval=60):
        self.app = app
        self.limit = limit
        self.interval = interval
        self.requests = defaultdict(list)

    async def __call__(self, scope, receive, send):
        client_ip = scope.get("client", ("", ""))[0]
        current_time = time.time()

        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > current_time - self.interval]

        if len(self.requests[client_ip]) >= self.limit:
            response = Response(status=429, body=b"Too many requests")
            await response.send_asgi(send)  
            return 

        await self.app(scope, receive, send)  
