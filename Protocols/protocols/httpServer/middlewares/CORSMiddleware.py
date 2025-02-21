from ..Responses.Response import Response

class CORSMiddleware:
    def __init__(self, allowed_origins="*"):
        self.allowed_origins = allowed_origins.encode()

    async def __call__(self, scope, receive, send, next_middleware):
        async def custom_send(event):
            if event["type"] == "http.response.start":
                headers = dict(event.get("headers", []))
                headers[b"access-control-allow-origin"] = self.allowed_origins
                headers[b"access-control-allow-methods"] = b"GET, POST, PUT, DELETE, OPTIONS"
                headers[b"access-control-allow-headers"] = b"Content-Type, Authorization"
                headers[b"access-control-allow-credentials"] = b"true"
                event["headers"] = list(headers.items())
            await send(event)

        if scope.get("method", "") == "OPTIONS":
            response = Response(
                status=204,  # 204 é melhor para preflight requests
                headers=[
                    (b"access-control-allow-origin", self.allowed_origins),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"Content-Type, Authorization"),
                    (b"access-control-allow-credentials", b"true"),
                ],
                body=b"",
            )
            await response.send_asgi(send)
            return

        await next_middleware(scope, receive, custom_send)
