from typing import Any, Callable, Dict, List, Union
from urllib.parse import urlparse
import re

class Router:
    def __init__(self):
        self.routes: Dict[str, List[Dict[str, Union[str, Callable]]]] = {
            'GET': [],
            'POST': [],
            'PATCH': [],
            'PUT': [],
            'DELETE': [],
            'OPTION': []
        }
        self.regex_find_var_parameters = re.compile(r"/{(?P<type>\w+): (?P<name>\w+)}")

    def add_route(self, method: str, url: str, handler_function: Callable):
        if method not in self.routes:
            raise ValueError(f"Method {method} is not supported in Router.")
        self.routes[method].append({"path": url, "function": handler_function})

    def get(self, url: str):
        return self._method_decorator('GET', url)

    def post(self, url: str):
        return self._method_decorator('POST', url)

    def patch(self, url: str):
        return self._method_decorator('PATCH', url)

    def put(self, url: str):
        return self._method_decorator('PUT', url)

    def delete(self, url: str):
        return self._method_decorator('DELETE', url)

    def option(self, url: str):
        return self._method_decorator('OPTION', url)

    def _method_decorator(self, method: str, url: str):
        def decorator(func):
            self.add_route(method, url, func)
            return func
        return decorator

    def find_matching_route(self, method: str, path: str) -> List[Dict[str, Union[str, Callable]]]:
        result = []
        for route in self.routes[method]:
            parsed_url = urlparse(path).path
            parsed_url_parts = [part for part in parsed_url.split("/") if part]
            # ---
            parsed_url_method = urlparse(route['path']).path
            parsed_url_method_parts = [part for part in parsed_url_method.split("/") if part]

            matches = self.regex_find_var_parameters.findall(route['path'])

            if len(parsed_url_parts) != len(parsed_url_method_parts): # Different number of path segments, not a match
                continue

            is_match = True
            for i in range(len(parsed_url_method_parts)):
                method_part = parsed_url_method_parts[i]
                request_part = parsed_url_parts[i]

                if not self.regex_find_var_parameters.match(f"/{method_part}") and method_part != request_part:
                    is_match = False # Literal path segment mismatch
                    break

            if is_match: # All segments matched (literal or parameter)
                result.append(route)
        return result

    def extract_params_from_patern_in_url(self, url: str, method_url: str) -> Dict[str, Any]:
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
            return {}

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
