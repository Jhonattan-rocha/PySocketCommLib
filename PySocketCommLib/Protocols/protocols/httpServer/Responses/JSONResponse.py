import json
from typing import Dict, Any, Callable
from .Response import Response

class JSONResponse(Response):
    def __init__(self, data: Any, status: int = 200, headers: Dict[str, str] = None):
        body = json.dumps(data).encode('utf-8')
        super().__init__(body=body, status=status, headers=headers, content_type='application/json')

    async def send_asgi(self, send: Callable):
        await send({
            'type': 'http.response.start',
            'status': self.status,
            'headers': [(k.encode('utf-8'), v.encode('utf-8')) for k, v in self.headers.items()],
        })
        await send({
            'type': 'http.response.body',
            'body': self.body,
        })