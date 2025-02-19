import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
import inspect
import logging
import mimetypes
import os
import ssl
from urllib.parse import urlparse
import re
from typing import Any, Callable, Dict, List, Tuple, Union
from Protocols.protocols.httpServer.Responses import FileResponse, RedirectResponse, JSONResponse, Response
from Protocols.protocols.httpServer.Router.Router import Router

class HttpServerProtocol:
    def __init__(self, host: str = 'localhost', port: int = 8080, logging_path: str = "./http_server.log", static_dir: str = "./static", use_https: bool = False, certfile: str = "", keyfile: str = "") -> None:
        self.host: str = host
        self.port: str = port
        self.static_dir = static_dir
        self.regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")
        self.middlewares = []
        self.use_https = use_https
        self.certfile = certfile
        self.keyfile = keyfile
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

    def add_middleware(self, middleware: Callable):
        self.middlewares.append(middleware)

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

        if self.use_https:
            if not self.certfile or not self.keyfile:
                raise ValueError("Certificado SSL não fornecido!")
            
            if not os.path.exists(self.keyfile) or not os.path.exists(self.certfile):
                self.logger.info(f"Bad path for key or certfile")
                raise FileNotFoundError("Key or certfile not found")
            
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            self.logger.info(f"Starting https server on {self.host}:{self.port}")
        else:  
            self.logger.info(f"Starting http server on {self.host}:{self.port}")
            httpd.serve_forever()

    def parse_path(self, handler: http.server.BaseHTTPRequestHandler) -> Tuple[str, Dict[str, str]]:
        url_components = urlparse(handler.path)
        path: str = url_components.path
        query_params = dict([param.split('=') for param in url_components.query.split('&') if '=' in param])
        return path, query_params

    def find_functions_to_run(self, method: str, path: str) -> List[Dict[str, Union[str, Callable]]]:
        """
        Encontra funções que correspondem a uma rota. Dá prioridade a correspondências exatas.
        """
        all_functions = []

        # Primeiro, busca em Routers
        for router in self.routers:
            all_functions.extend(router.find_matching_route(method, path))

        # Depois, busca em handlers adicionados manualmente
        all_functions.extend(self.http_server_methods[method])

        # Se houver uma correspondência exata, retorna apenas essa
        exact_matches = [f for f in all_functions if f["path"] == path]
        if exact_matches:
            return exact_matches

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
            def handle_method(handler, method):
                server_instance._handle_method(handler, method)

            def do_GET(handler):
                handler.handle_method('GET')

            def do_POST(handler):
                handler.handle_method('POST')

            def do_PATCH(handler):
                handler.handle_method('PATCH')

            def do_PUT(handler):
                handler.handle_method('PUT')

            def do_DELETE(handler):
                handler.handle_method('DELETE')

            def log_message(handler, format: str, *args):
                server_instance.logger.info(f"Request: {handler.client_address} - {format % args}")


        return HTTPRequestHandler


    def _handle_method(self, handler: http.server.BaseHTTPRequestHandler, method: str):
        path, query_params = self.parse_path(handler)
        executor = ThreadPoolExecutor()

        for middleware in self.middlewares:
            middleware(handler, path, method)

        if self.is_static_file(path):
            self.serve_static_file(handler, path)
            return

        functions_to_run = self.find_functions_to_run(method, path)
    
        if not functions_to_run:
            Response(body=b'Method Not Allowed - No matching route', status=404).send(handler)
            return

        for function_data in functions_to_run:
            vars = {}

            if function_data['path'] != path:
                if self.regex_find_var_parameters.search(function_data['path']):
                    try:
                        vars = Router().extract_params_from_patern_in_url(path, function_data['path'])
                    except Exception as e:
                        continue

            params = [path, query_params, vars]
            try:
                func = function_data['function']
                
                if inspect.iscoroutinefunction(func):
                    asyncio.run(self._run_async_handler(func, handler, params))
                else:
                    def exe():
                        response = func(handler, params=params)
                        
                        if isinstance(response, Response):
                            response.send(handler)
                            return # Stop processing after the first route sends a response
                        else:
                            Response(body=b'Server handled request, response was not explicitly created.', status=200).send(handler)
                            return # Stop processing even if old style handler     

                    executor.submit(exe)           
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
