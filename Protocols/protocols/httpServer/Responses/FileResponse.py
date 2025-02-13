import json, os, mimetypes, http
from typing import Dict
from Protocols.protocols.httpServer.Responses.Response import Response


class FileResponse(Response):
    def __init__(self, file_path: str, status: int = 200, headers: Dict[str, str] = None, content_type: str = None):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        self.file_path = file_path
        custom_headers = headers if headers else {}
        custom_headers['Content-type'] = content_type if content_type else mime_type
        super().__init__(status=status, headers=custom_headers, content_type=mime_type) # Content type is already set in headers, but kept for clarity

    def send(self, handler: http.server.BaseHTTPRequestHandler):
        try:
            with open(self.file_path, 'rb') as f:
                handler.send_response(self.status)
                for key, value in self.headers.items():
                    handler.send_header(key, value)
                handler.end_headers()
                handler.wfile.write(f.read())
        except Exception as e:
            handler.send_error(500, f"Error reading file: {e}")
