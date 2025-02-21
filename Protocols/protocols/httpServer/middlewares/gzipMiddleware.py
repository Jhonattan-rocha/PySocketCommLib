import gzip

class GzipMiddleware:
    async def __call__(self, scope, receive, send):
        async def custom_send(event):
            if event["type"] == "http.response.body":
                event["body"] = gzip.compress(event["body"])
                event["headers"].append((b'Content-Encoding', b'gzip'))
            await send(event)

        await self.app(scope, receive, custom_send)
