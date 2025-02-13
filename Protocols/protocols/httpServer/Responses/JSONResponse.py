import json
from typing import Dict, Any
from Protocols.protocols.httpServer.Responses.Response import Response

class JSONResponse(Response):
    def __init__(self, data: Any, status: int = 200, headers: Dict[str, str] = None):
        body = json.dumps(data).encode('utf-8')
        super().__init__(body=body, status=status, headers=headers, content_type='application/json')
