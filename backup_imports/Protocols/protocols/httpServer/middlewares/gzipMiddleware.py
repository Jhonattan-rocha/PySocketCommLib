import gzip

class GzipMiddleware:
    def __init__(self, min_size=500):
        self.min_size = min_size

    async def __call__(self, scope, receive, send, next_middleware):
        async def custom_send(event):
            if event["type"] == "http.response.body" and len(event["body"]) >= self.min_size:
                compressed_body = gzip.compress(event["body"])
                headers = dict(event.get("headers", []))
                headers[b'Content-Encoding'] = b'gzip'
                event["headers"] = list(headers.items())
                event["body"] = compressed_body
            await send(event)

        await next_middleware(scope, receive, custom_send)
