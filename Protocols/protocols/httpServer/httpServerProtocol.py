import asyncio
import inspect
import logging
import mimetypes
import os
import re
from typing import Any, Callable, Dict, List, Tuple, Union
from .Responses import FileResponse
from .Responses import Response
from .Router.Router import Router

class AsyncHttpServerProtocol:
    def __init__(self, host: str = 'localhost', port: int = 8080, static_dir: str = "./static", use_https: bool = False, certfile: str = "", keyfile: str = "", lifespan: Callable = None, max_workers: int = 100) -> None:
        self.host: str = host
        self.port: int = port
        self.static_dir = static_dir
        self.request_queue = asyncio.Queue(maxsize=max_workers)
        self.max_workers = max_workers
        self.workers = []
        self.regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")
        self.use_https = use_https
        self.certfile = certfile
        self.keyfile = keyfile
        self.lifespan = lifespan
        self.logger = logging.getLogger("httpServer")
        self.routers: List[Router] = [] # List to hold registered routers
        self.http_server_methods = { # Keep for direct handlers if needed, or deprecate
            'GET': [],
            'POST': [],
            'PATCH': [],
            'PUT': [],
            'DELETE': [],
            'OPTION': []
        }
        self.startup_tasks = []  # Lista de funções de inicialização
        self.shutdown_tasks = []  # Lista de funções de encerramento

    def on_startup(self, func: Callable):
        """Registra uma função a ser chamada na inicialização."""
        self.startup_tasks.append(func)

    def on_shutdown(self, func: Callable):
        """Registra uma função a ser chamada no encerramento."""
        self.shutdown_tasks.append(func)

    async def start_workers(self):
        """Inicia workers para processar as requisições na fila."""
        for _ in range(self.max_workers):
            self.workers.append(asyncio.create_task(self.worker()))
    
    async def worker(self):
        """Processa requisições da fila de forma segura."""
        while True:
            try:
                scope, receive, send = await self.request_queue.get()
                if not scope:
                    continue
                
                self.logger.info(f"Processandoa request: {scope}")
                await self.handle_asgi_request(scope, receive, send)
            except Exception as e:
                self.logger.error(f"Erro no processamento da requisição: {e}")
                response = Response(status=500, body=f"Server Internal Error: {e}".encode())
                await response.send_asgi(send)
            finally:
                self.request_queue.task_done()
                
    async def startup(self):
        """Executa todas as funções registradas para inicialização."""
        await self.start_workers()
        
        for task in self.startup_tasks:
            if inspect.iscoroutinefunction(task):
                await task()
            else:
                task()
        
    async def shutdown(self):
        """Executa todas as funções registradas para encerramento."""
        for task in self.workers:
            task.cancel()
        for task in self.shutdown_tasks:
            if inspect.iscoroutinefunction(task):
                await task()
            else:
                task()
                
    def register_router(self, router: Router):
        """Registers a Router instance to be used by the server."""
        self.routers.append(router)

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """
        Suporte ao ciclo de vida ASGI (lifespan, http).
        """
        if scope['type'] == 'lifespan':
            async with self.lifespan(self):  # Inicia o ciclo de vida corretamente
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        break  # Sai do loop quando o servidor for encerrado
        elif scope['type'] == 'http':
            if not self.request_queue:
                self.logger.error("Fila de requisições não foi inicializada!")
                response = Response(status=500, body=b"Server Error: Request queue not initialized")
                await response.send_asgi(send)

            await self.request_queue.put((scope, receive, send))
            
            await asyncio.sleep(5)
        else:
            raise ValueError(f"Unsupported scope type: {scope['type']}")

    async def handle_asgi_request(self, scope: dict, receive: Callable, send: Callable):
        """Garante que toda requisição receba uma resposta"""
        try:
            method = scope["method"]
            raw_path = scope.get("raw_path", b"/").decode("utf-8")
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = dict([param.split("=") for param in query_string.split("&") if "=" in param])

            if self.is_static_file(raw_path):
                await self.serve_static_file_asgi(scope, receive, send, raw_path)
                return

            functions_to_run = self.find_functions_to_run(method, raw_path)

            if not functions_to_run:
                response = Response(body=b"Method Not Allowed - No matching route", status=404)
                await response.send_asgi(send)
                return

            for function_data in functions_to_run:
                vars = {}
                if function_data["path"] != raw_path:
                    if self.regex_find_var_parameters.search(function_data["path"]):
                        try:
                            vars = Router().extract_params_from_patern_in_url(raw_path, function_data["path"])
                        except Exception as e:
                            continue

                params = [raw_path, query_params, vars]
                func = function_data["function"]

                response = Response()
                
                if inspect.iscoroutinefunction(func):
                    response = await func(params=params)
                else:
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(None, func, params)

                if isinstance(response, Response):
                    await response.send_asgi(send)
                    return
                
                if not response:
                    return

                response_error = Response(body=b"Server handled request, but no response was explicitly created.", status=200)
                await response_error.send_asgi(send)
                return

        except Exception as e:
            self.logger.error(f"Erro ao processar requisição: {e}")
            response = Response(status=500, body=f"Internal Server Error: {e}".encode("utf-8"))
            await response.send_asgi(send)


    def parse_path(self, scope: dict) -> Tuple[str, Dict[str, str]]:
        """
        Parses path from ASGI scope - not directly used anymore, path is parsed in handle_asgi_request
        Kept for potential internal utility if needed, but ASGI scope path parsing is now in handle_asgi_request.
        """
        raw_path = scope.get('raw_path', b'/') # raw_path is bytes
        path = raw_path.decode('utf-8') # Decode bytes to string
        query_string = scope.get('query_string', b'').decode('utf-8') # Decode bytes to string
        query_params = dict([param.split('=') for param in query_string.split('&') if '=' in param])
        return path, query_params

    def find_functions_to_run(self, method: str, path: str) -> List[Dict[str, Union[str, Callable]]]:
        """
        Finds functions that match a route. Gives priority to exact matches.
        """
        all_functions = []

        # First, search in Routers
        for router in self.routers:
            all_functions.extend(router.find_matching_route(method, path))

        # Then, search in manually added handlers (direct routes)
        all_functions.extend(self.http_server_methods[method])

        # If there is an exact match, return only that
        exact_matches = [f for f in all_functions if f["path"] == path]
        if exact_matches:
            return exact_matches

        return all_functions


    def is_static_file(self, path: str) -> bool:
        """
        Checks if the request path is for a static file.
        """
        # Typical static file extensions
        static_extensions = ['.ico', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js']

        # Checks if the path has a static file extension
        return any(path.endswith(ext) for ext in static_extensions)


    async def serve_static_file_asgi(self, scope: dict, receive: Callable, send: Callable, path: str):
        """
        Serves static files from the 'static' folder for ASGI.
        """
        # Remove the initial slash (/) to access the relative path
        if path.startswith('/'):
            path = path[1:]

        # Generate the full path to the static file
        file_path = os.path.join(self.static_dir, path)

        try:
            # Check if the file exists and is a file
            if os.path.exists(file_path) and os.path.isfile(file_path):
                # Determine the MIME type of the file
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = 'application/octet-stream'  # Generic type if not possible to determine

                # Send the file response using  FileResponse (ASGI adapted)
                file_response = FileResponse(file_path=file_path) #  FileResponse needs to be ASGI adapted
                await file_response.send_asgi(send) # Adapt  FileResponse.send for ASGI

            else:
                # File not found
                response = Response(body=b'File Not Found', status=404)
                await response.send_asgi(send) # Adapt Response.send for ASGI

        except Exception as e:
            # Error handling
            self.logger.error(f"Error serving static file {file_path}: {e}")
            response = Response(status=500)
            await response.send_asgi(send) # Adapt Response.send for ASGI # Generic 500 error

    def add_handler(self, method: str, url: str):
        if method not in self.http_server_methods:
            raise ValueError(f"Method {method} is not supported.")

        def decorator(func):
            self.http_server_methods[method].append({"path": url, "function": func})
            return func

        return decorator

    # --- Decorators for HttpServerProtocol for direct route handling ---
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
