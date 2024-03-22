import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
from typing import Any, Callable

class HttpProtocol:
    def __init__(self, host: str='localhost', port: int=8080) -> None:
        self.host = host
        self.port = port
        self.__http_server_methods = {
            'GET': None,
            'POST': None,
            'PATCH': None,
            'PUT': None,
            'DELETE': None
        }
    
    def request(self, method: str, url: str, headers: dict[str, str]=None, body: str | None=None) -> http.client.HTTPResponse:
        url_parts = http.client.urlsplit(url)
        host = url_parts.netloc
        path = url_parts.path

        if url_parts.scheme == 'https':
            conn = http.client.HTTPSConnection(host)
        else:
            conn = http.client.HTTPConnection(host)

        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        return response
    
    def start_http_server(self):
        server_address = (self.host, self.port)
        handler_class = self._make_http_handler()
        httpd = http.server.HTTPServer(server_address, handler_class)
        httpd.serve_forever()
        
    def _make_http_handler(self):
        class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                self.__http_server_methods['GET'](handler)

            def do_POST(handler):
                self.__http_server_methods['POST'](handler)

            def do_PATCH(handler):
                self.__http_server_methods['PATCH'](handler)
            
            def do_PUT(handler):
                self.__http_server_methods['PUT'](handler)
            
            def do_DELETE(handler):
                self.__http_server_methods['DELETE'](handler)

        return HTTPRequestHandler
    
    def add_handler(self, method: str):
        def decorator(func):
            self._http_server_methods[method] = func
            return func
        return decorator

    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res
