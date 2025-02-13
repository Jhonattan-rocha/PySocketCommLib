from typing import Dict
import http

class Response:
    def __init__(self, body: bytes = b'', status: int = 200, headers: Dict[str, str] = None, content_type: str = 'text/html'):
        self.body = body
        self.status = status
        self.headers = headers or {}
        self.headers['Content-type'] = content_type

    def send(self, handler: http.server.BaseHTTPRequestHandler):
        handler.send_response(self.status)
        for key, value in self.headers.items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(self.body)