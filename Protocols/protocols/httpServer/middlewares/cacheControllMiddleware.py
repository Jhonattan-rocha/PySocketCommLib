class CacheControlMiddleware:
    def __init__(self, cache_time=3600):
        self.cache_time = cache_time

    async def __call__(self, scope, receive, send, next_middleware):
        async def custom_send(event):
            if event["type"] == "http.response.start":
                event["headers"].append((b"Cache-Control", f"max-age={self.cache_time}".encode()))
            await send(event)

        await next_middleware(scope, receive, custom_send)
