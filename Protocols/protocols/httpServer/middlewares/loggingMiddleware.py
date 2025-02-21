import time
import logging

class LoggingMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("httpServer")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    async def __call__(self, scope, receive, send):
        start_time = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "")

        self.logger.info(f"Recebendo {method} {path}")

        async def custom_send(event):
            if event["type"] == "http.response.start":
                status_code = event["status"]
                self.logger.info(f"Respondendo {method} {path} com status {status_code} em {time.time() - start_time:.4f}s")
            await send(event)

        await self.app(scope, receive, custom_send)
