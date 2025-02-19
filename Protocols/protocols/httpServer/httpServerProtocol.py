import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
import inspect
import logging
import mimetypes
import os
from urllib.parse import urlparse
import re
from typing import Any, Callable, Dict, List, Tuple, Union
from Protocols.protocols.httpServer.Responses import FileResponse, RedirectResponse, JSONResponse, Response
from Protocols.protocols.httpServer.Router import Router

class HttpServerProtocol:
    def __init__(self, host: str = 'localhost', port: int = 8080, logging_path: str = "./http_server.log", static_dir: str = "./static") -> None:
        self.host: str = host
        self.port: str = port
        self.static_dir = static_dir
        self.regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")
        logging.basicConfig(filename=logging_path, level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.routers: List[Router] = [] # List to hold registered routers
        self.http_server_methods = { # Keep for direct handlers if needed, or deprecate
            'GET': [],
            'POST': [],
            'PATCH': [],
            'PUT': [],
            'DELETE': [],
            'OPTION': []
        }

    def register_router(self, router: Router):
        """Registers a Router instance to be used by the server."""
        self.routers.append(router)

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

    def parse_path(self, handler: http.server.BaseHTTPRequestHandler) -> Tuple[str, Dict[str, str]]:
        url_components = urlparse(handler.path)
        path: str = url_components.path
        query_params = dict([param.split('=') for param in url_components.query.split('&') if '=' in param])
        return path, query_params

    def find_functions_to_run(self, method: str, path: str) -> List[Dict[str, Union[str, Callable]]]:
        """
        Finds route handlers from both HttpServerProtocol's direct methods and registered Routers.
        Prioritizes Router routes if there's a conflict (you might adjust this logic).
        """
        all_functions = []

        # Check registered Routers first
        for router in self.routers:
            all_functions.extend(router.find_matching_route(method, path))

        # Then check HttpServerProtocol's direct methods (optional, you might remove this in favor of only using Routers)
        all_functions.extend(self.http_server_methods[method])

        return all_functions


    def is_static_file(self, path: str) -> bool:
        """
        Verifica se o caminho da requisição é para um arquivo estático.
        """
        # Extensões típicas de arquivos estáticos
        static_extensions = ['.ico', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js']

        # Verifica se o caminho tem uma extensão de arquivo estático
        return any(path.endswith(ext) for ext in static_extensions)


    def serve_static_file(self, handler: http.server.BaseHTTPRequestHandler, path: str):
        """
        Serve arquivos estáticos a partir da pasta 'static'.
        """
        # Remove a barra inicial (/) para acessar o caminho relativo
        if path.startswith('/'):
            path = path[1:]

        # Gera o caminho completo para o arquivo estático
        file_path = os.path.join(self.static_dir, path)

        try:
            # Verifica se o arquivo existe
            if os.path.exists(file_path) and os.path.isfile(file_path):
                # Determina o tipo MIME do arquivo
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = 'application/octet-stream'  # Tipo genérico se não for possível determinar

                # Lê o arquivo e envia a resposta using FileResponse
                FileResponse(file_path=file_path).send(handler)

            else:
                # Arquivo não encontrado
                Response(body=b'File Not Found', status=404).send(handler)

        except Exception as e:
            # Tratamento de erro
            self.logger.error(f"Error serving static file {file_path}: {e}")
            Response(status=500).send(handler) # Generic 500 error


    def _make_http_handler(self):
        server_instance = self # Capture HttpServerProtocol instance

        class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                server_instance._handle_method(handler, 'GET')

            def do_POST(handler):
                server_instance._handle_method(handler, 'POST')

            def do_PATCH(handler):
                server_instance._handle_method(handler, 'PATCH')

            def do_PUT(handler):
                server_instance._handle_method(handler, 'PUT')

            def do_DELETE(handler):
                server_instance._handle_method(handler, 'DELETE')

            def log_message(handler, format: str, *args):
                server_instance.logger.info(f"Request: {handler.client_address} - {format % args}")

        return HTTPRequestHandler


    def _handle_method(self, handler: http.server.BaseHTTPRequestHandler, method: str):
        path, query_params = self.parse_path(handler)

        if self.is_static_file(path):
            self.serve_static_file(handler, path)
            return

        functions_to_run = self.find_functions_to_run(method, path)

        if not functions_to_run:
            Response(body=b'Method Not Allowed - No matching route', status=404).send(handler)
            return

        for function_data in functions_to_run:
            vars = {} 
            if self.regex_find_var_parameters.search(function_data['path']):
                try:
                    vars = Router().extract_params_from_patern_in_url(path, function_data['path'])
                except ValueError as e:
                    continue
                    
            params = [path, query_params, vars]
            try:
                func = function_data['function']
                
                if inspect.iscoroutinefunction(func):
                    asyncio.create_task(self._run_async_handler(func, handler, params))
                else:
                    response = func(handler, params=params)
                    
                    if isinstance(response, Response):
                        response.send(handler)
                        return # Stop processing after the first route sends a response
                    else:
                        Response(body=b'Server handled request, response was not explicitly created.', status=200).send(handler)
                        return # Stop processing even if old style handler                
            except Exception as e:
                self.logger.error(f"Error executing handler function: {e}")
                Response(status=500, body=f"Server Error: {e}".encode('utf-8')).send(handler)
                return # Stop processing on error as well

    async def _run_async_handler(self, func, handler, params):
        """
        Executa handlers assíncronos dentro do loop do servidor corretamente.
        """
        try:
            response = await func(handler, params=params)
            if isinstance(response, Response):
                response.send(handler)
            else:
                Response(body=b'Server handled request, response was not explicitly created.', status=200).send(handler)
                return # Stop processing even if old style handler   
                
        except Exception as e:
            self.logger.error(f"Erro no handler async: {e}")
            Response(status=500, body=f"Server Error: {e}".encode('utf-8')).send(handler)
            
    def add_handler(self, method: str, url: str):
        if method not in self.http_server_methods:
            raise ValueError(f"Method {method} is not supported.")

        def decorator(func):
            self.http_server_methods[method].append({"path": url, "function": func})
            return func

        return decorator

    # --- Decorators for HttpServerProtocol for direct route handling (optional now with Router) ---
    def get(self, url: str):
        return self.add_handler('GET', url)

    def post(self, url: str):
        return self.add_handler('POST', url)

    def patch(self, url: str):
        return self.add_handler('PATCH', url)

    def put(self, url: str):
        return self.add_handler('PUT', url)

    def delete(self, url: str):
        return self.add_handler('DELETE', url)

    def option(self, url: str):
        return self.add_handler('OPTION', url)


    async def async_executor(self, call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, call, *args)
        return res


if __name__ == '__main__':
    server = HttpServerProtocol()
    my_router = Router()

    @my_router.get("/")
    def index_route(handler, params):
        return Response(body=b"Hello from the Router index!", content_type='text/plain')

    @my_router.get("/users")
    def users_route(handler, params):
        data = {"users": ["Alice", "Bob"]}
        return JSONResponse(data=data)

    @my_router.get("/files/{str:filename}")
    def file_route(handler, params):
        filename = params[2].get('filename')
        filepath = os.path.join(server.static_dir, filename)
        try:
            return FileResponse(filepath)
        except FileNotFoundError:
            return Response(body=b"File not found", status=404)


    @server.get("/direct_route")
    def direct_handler(handler, params):
        return Response(body=b"Hello from direct route!", content_type='text/plain')


    server.register_router(my_router) # Register the router

    server.start_http_server()
