import time
import logging

class LoggingMiddleware:
    def __init__(self):
        self.logger = logging.getLogger("httpServer")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    async def __call__(self, scope, receive, send, next_middleware):
        start_time = time.time()
        method = scope.get("method", "").upper()
        path = scope.get("path", "")

        self.logger.info(f"Recebendo {method} {path}")

        async def custom_send(event):
            if event["type"] == "http.response.start":
                status_code = event.get("status", 500)
                duration = time.time() - start_time
                self.logger.info(f"Respondendo {method} {path} com status {status_code} em {duration:.4f}s")
            await send(event)

        await next_middleware(scope, receive, custom_send)
