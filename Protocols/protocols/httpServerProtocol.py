import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
import logging
import mimetypes
import os
from urllib.parse import urlparse
import re
from typing import Any, Callable


class HttpServerProtocol:
    def __init__(self, host: str = 'localhost', port: int = 8080, logging_path: str = "./server.log", static_dir: str = "./static") -> None:
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")
        logging.basicConfig(filename=logging_path, level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.http_server_methods = {
            'GET': [],
            'POST': [],
            'PATCH': [],
            'PUT': [],
            'DELETE': [],
            'OPTION': []
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
    
    def extract_params_from_patern_in_url(self, url: str, method_url: str):
        type_mapping = {
            'int': int,
            'str': str,
            'float': float,
            'bool': bool
        }
        parsed_url = urlparse(url)
        path = parsed_url.path
        path_parts = [part for part in path.split("/") if part]
        matches = self.regex_find_var_parameters.findall(method_url)
        values = path_parts[-len(matches):]
        if not matches:
            raise ValueError("Nenhuma variável encontrada na URL.")
        
        parsed_vars = {}
        
        for i in range(max(len(matches), len(values))):
            var_type, var_name = matches[i]
            value = values[i]
            try:
                parsed_vars[var_name] = type_mapping[var_type](value)
            except KeyError:
                raise ValueError(f"Tipo {var_type} não suportado.")
            except ValueError:
                raise ValueError(f"Falha ao converter '{value}' para {var_type}.")
        
        return parsed_vars
    
    def parse_path(self, handler):
        url_components = urlparse(handler.path)
        path: str = url_components.path
        query_params = dict([param.split('=') for param in url_components.query.split('&') if '=' in param])
        return [path, query_params]

    def find_functions_to_run(self, method: str, path: str):
        result = []
        for funciton in self.http_server_methods[method]:
            parsed_url = urlparse(path).path
            parsed_url_parts = [part for part in parsed_url.split("/") if part]
            # ---
            parsed_url_method = urlparse(funciton['path']).path
            parsed_url_method_parts = [part for part in parsed_url_method.split("/") if part]

            matches = self.regex_find_var_parameters.findall(funciton['path'])

            if len(parsed_url_parts) != len(parsed_url_method_parts):
                print(parsed_url_parts, parsed_url_method_parts)
                raise ValueError(f"Invalid url varible, expected {len(matches)} varibles, but was passed {(len(parsed_url_parts)-(len(parsed_url_method_parts)-len(matches)))}")
            
            if path == funciton['path'] or parsed_url_parts[:len(parsed_url_method_parts)-len(matches)] == parsed_url_method_parts[:len(parsed_url_method_parts)-len(matches)]:
                result.append(funciton)
        return result
    
    def is_static_file(self, path: str) -> bool:
        """
        Verifica se o caminho da requisição é para um arquivo estático.
        """
        # Extensões típicas de arquivos estáticos
        static_extensions = ['.ico', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js']
        
        # Verifica se o caminho tem uma extensão de arquivo estático
        return any(path.endswith(ext) for ext in static_extensions)


    def serve_static_file(self, handler, path: str):
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
                
                # Lê o arquivo e envia a resposta
                with open(file_path, 'rb') as f:
                    handler.send_response(200)
                    handler.send_header('Content-type', mime_type)
                    handler.end_headers()
                    handler.wfile.write(f.read())
            else:
                # Arquivo não encontrado
                handler.send_response(404)
                handler.send_header('Content-type', 'text/html')
                handler.end_headers()
                handler.wfile.write(b'File Not Found')
        except Exception as e:
            # Tratamento de erro
            self.logger.error(f"Error serving static file {file_path}: {e}")
            handler.send_response(500)
            handler.end_headers()


    def _make_http_handler(self):
        class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler):
                if self.http_server_methods['GET']:
                    if self.is_static_file(handler.path):
                        self.serve_static_file(handler, handler.path)
                        return
                    params = self.parse_path(handler)
                    result = self.find_functions_to_run('GET', params[0])
                    for function in result:
                        vars = self.extract_params_from_patern_in_url(params[0], function['path'])
                        params.append(vars)
                        function['function'](handler, params=params)
                        params.pop()
                else:
                    handler.send_response(404)
                    handler.send_header('Content-type', 'text/html')
                    handler.end_headers()
                    handler.wfile.write(b'Method Not Allowed')

            def do_POST(handler):
                params = self.parse_path(handler)
                if self.http_server_methods['POST']:
                    params = self.parse_path(handler)
                    result = self.find_functions_to_run('POST', params[0])
                    for function in result:
                        vars = self.extract_params_from_patern_in_url(params[0], function['path'])
                        params.append(vars)
                        function['function'](handler, params=params)
                        params.pop()
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_PATCH(handler):
                params = self.parse_path(handler)
                if self.http_server_methods['PATCH']:
                    params = self.parse_path(handler)
                    result = self.find_functions_to_run('PATCH', params[0])
                    for function in result:
                        vars = self.extract_params_from_patern_in_url(params[0], function['path'])
                        params.append(vars)
                        function['function'](handler, params=params)
                        params.pop()
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_PUT(handler):
                params = self.parse_path(handler)
                if self.http_server_methods['PUT']:
                    params = self.parse_path(handler)
                    result = self.find_functions_to_run('PUT', params[0])
                    for function in result:
                        vars = self.extract_params_from_patern_in_url(params[0], function['path'])
                        params.append(vars)
                        function['function'](handler, params=params)
                        params.pop()
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def do_DELETE(handler):
                params = self.parse_path(handler)
                if self.http_server_methods['DELETE']:
                    params = self.parse_path(handler)
                    result = self.find_functions_to_run('DELETE', params[0])
                    for function in result:
                        vars = self.extract_params_from_patern_in_url(params[0], function['path'])
                        params.append(vars)
                        function['function'](handler, params=params)
                        params.pop()
                else:
                    handler.send_response(404)
                    handler.send_header("Content-type", "text/html")
                    handler.end_headers()
                    handler.wfile.write(b"Method Not Allowed")

            def log_message(handler, format: str, *args):
                self.logger.info(f"Request: {handler.client_address} - {format % args}")

        return HTTPRequestHandler

    def add_handler(self, method: str, url: str):
        if method not in self.http_server_methods:
            raise ValueError(f"Method {method} is not supported.")

        def decorator(func):
            self.http_server_methods[method].append({"path": url, "function": func})
            return func

        return decorator

    async def async_executor(self, call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, call, *args)
        return res
