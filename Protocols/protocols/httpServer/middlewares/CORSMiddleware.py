from ..Responses.Response import Response

class CORSMiddleware:
    def __init__(self, allowed_origins="*"):
        self.allowed_origins = allowed_origins.encode()

    async def __call__(self, scope, receive, next):
        async def custom_send(event):
            if event["type"] == "http.response.start":
                headers = dict(event.get("headers", []))
                headers.setdefault(b"access-control-allow-origin", self.allowed_origins)
                headers.setdefault(b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS")
                headers.setdefault(b"access-control-allow-headers", b"Content-Type, Authorization")
                headers.setdefault(b"access-control-allow-credentials", b"true")
                event["headers"] = list(headers.items())
            await next()

        if scope["method"] == "OPTIONS":
            response = Response(
                status=200,
                headers=[
                    (b"access-control-allow-origin", self.allowed_origins),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"Content-Type, Authorization"),
                    (b"access-control-allow-credentials", b"true"),
                ],
                body=b"",
            )
            return response;            

        await next()
