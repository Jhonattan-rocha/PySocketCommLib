from typing import Dict, Callable
import logging
import uuid

class Response:
    def __init__(self, body: bytes = b'', status: int = 200, headers: Dict[str, str] = None, content_type: str = 'text/html'):
        self.body = body
        self.status = status
        self.uuid = uuid.uuid4().__str__()
        self.headers = headers or {}
        self.headers['Content-type'] = content_type
        self.logger = logging.getLogger("httpServer")

    async def send_asgi(self, send: Callable):
        try:
            await send({
                'type': 'http.response.start',
                'status': self.status,
                'headers': [(k.encode('utf-8'), v.encode('utf-8')) for k, v in self.headers.items()],
            })
            await send({
                'type': 'http.response.body',
                'body': self.body,
            })
        except Exception as e:
            self.logger.error(f"Erro ao processar requisição: {e}")
            return