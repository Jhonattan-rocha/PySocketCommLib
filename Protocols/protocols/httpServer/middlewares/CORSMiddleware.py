class CORSMiddleware:
    def __init__(self, app, allowed_origins="*"):
        self.app = app
        self.allowed_origins = allowed_origins

    async def __call__(self, scope, receive, send):
        response_started = False  # Variável para rastrear se a resposta já começou

        async def custom_send(event):
            nonlocal response_started
            if event["type"] == "http.response.start" and not response_started:
                event["headers"].append((b"Access-Control-Allow-Origin", self.allowed_origins.encode()))
                response_started = True  # Marca que a resposta começou
            await send(event)

        await self.app(scope, receive, custom_send)
