from typing import Dict, Any
from Protocols.protocols.httpServer.Responses.Response import Response

class RedirectResponse(Response):
    def __init__(self, url: str, status: int = 302, headers: Dict[str, str] = None): # 302 Found is a common redirect status
        custom_headers = headers if headers else {}
        custom_headers['Location'] = url
        super().__init__(status=status, headers=custom_headers, content_type='text/html')
        self.body = f"<html><head><meta http-equiv='refresh' content='0;url={url}'></head><body><a href='{url}'>Redirecting to {url}</a></body></html>".encode('utf-8')
