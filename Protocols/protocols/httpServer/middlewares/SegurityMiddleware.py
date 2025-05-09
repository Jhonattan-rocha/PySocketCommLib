from ..Responses.Response import Response

class SecurityMiddleware:
    def __init__(self):
        self.security_headers = [
            (b"X-Frame-Options", b"DENY"),
            (b"X-Content-Type-Options", b"nosniff"),
            (b"Referrer-Policy", b"no-referrer"),
        ]

    async def __call__(self, scope, receive, send, next_middleware):
        async def custom_send(event):
            if event["type"] == "http.response.start":
                event["headers"].extend(self.security_headers)
            await send(event)

        await next_middleware(scope, receive, custom_send)
