import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
import logging
from typing import Any, Callable


class HttpServerProtocol:
    def __init__(self, host: str = 'localhost', port: int = 8080, logging_path: str = "./server.log") -> None:
        self.host = host
        self.port = port
        logging.basicConfig(filename=logging_path, level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.__http_server_methods = {
            'GET': None,
            'POST': None,
            'PATCH': None,
            'PUT': None,
            'DELETE': None
        }

    def request(self, method: str, url: str, headers: dict[str, str] = None,
                body: str = None) -> http.client.HTTPResponse:
        """
        Sends an HTTP request and returns the response.

        :param method: HTTP method (GET, POST, etc.)
        :param url: URL to send the request to
        :param headers: Optional headers to include in the request
        :param body: Optional body for the request
        :return: HTTPResponse object
        """
        url_parts = http.client.urlsplit(url)
        host = url_parts.netloc
        path = url_parts.path

        try:
            if url_parts.scheme == 'https':
                conn = http.client.HTTPSConnection(host)
            else:
                conn = http.client.HTTPConnection(host)

            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            raise

    def start_http_server(self):
        server_address = (self.host, self.port)
        handler_class = self._make_http_handler()
        httpd = http.server.HTTPServer(server_address, handler_class)
        self.logger.info(f"Starting server on {self.host}:{self.port}")
        httpd.serve_forever()

    def _make_http_handler(self):
        class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                if self.__http_server_methods['GET']:
                    self.__http_server_methods['GET'](handler)
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_POST(handler):
                if self.__http_server_methods['POST']:
                    self.__http_server_methods['POST'](handler)
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_PATCH(handler):
                if self.__http_server_methods['PATCH']:
                    self.__http_server_methods['PATCH'](handler)
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_PUT(handler):
                if self.__http_server_methods['PUT']:
                    self.__http_server_methods['PUT'](handler)
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_DELETE(handler):
                if self.__http_server_methods['DELETE']:
                    self.__http_server_methods['DELETE'](handler)
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def log_message(handler, format: str, *args):
                self.logger.info(f"Request: {handler.client_address} - {format % args}")

        return HTTPRequestHandler

    def add_handler(self, method: str):
        if method not in self.__http_server_methods:
            raise ValueError(f"Method {method} is not supported.")

        def decorator(func):
            self.__http_server_methods[method] = func
            return func

        return decorator

    async def async_executor(self, call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, call, *args)
        return res
