"""Health Endpoints Module

Implementa endpoints HTTP para monitoramento:
- /health - Health check básico
- /health/live - Liveness probe
- /health/ready - Readiness probe
- /metrics - Métricas em formato Prometheus
- /status - Status detalhado do sistema
"""

import json
import time
from typing import Dict, Any, Optional, Callable, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from ..health.checker import HealthChecker
from ..health.readiness import ReadinessChecker
from ..metrics.collector import MetricsCollector
from ..log_utils.structured_logger import StructuredLogger


class HealthEndpoints:
    """Endpoints HTTP para monitoramento"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Componentes de monitoramento
        self.health_checker = HealthChecker()
        self.readiness_checker = ReadinessChecker()
        self.metrics_collector = MetricsCollector()
        self.logger = StructuredLogger()
        
        # Configurações
        self.enable_detailed_metrics = True
        self.enable_system_info = True
        self.cors_enabled = True
        
        # Handlers personalizados
        self.custom_handlers: Dict[str, Callable] = {}
    
    def add_custom_handler(self, path: str, handler: Callable[[Dict[str, Any]], Tuple[int, Dict[str, Any]]]) -> None:
        """Adiciona handler personalizado
        
        Args:
            path: Caminho do endpoint (ex: '/custom/endpoint')
            handler: Função que recebe query params e retorna (status_code, response_data)
        """
        self.custom_handlers[path] = handler
    
    def start(self) -> None:
        """Inicia o servidor de endpoints"""
        if self.running:
            return
        
        # Cria classe de handler com referência a esta instância
        endpoints_instance = self
        
        class MonitoringHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.endpoints = endpoints_instance
                super().__init__(*args, **kwargs)
            
            def log_message(self, format, *args):
                # Usa nosso logger estruturado
                self.endpoints.logger.debug(f"HTTP {format % args}")
            
            def _send_response(self, status_code: int, data: Dict[str, Any], 
                             content_type: str = 'application/json') -> None:
                """Envia resposta HTTP"""
                self.send_response(status_code)
                
                # Headers CORS se habilitado
                if self.endpoints.cors_enabled:
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                
                if content_type == 'application/json':
                    response_body = json.dumps(data, ensure_ascii=False, indent=2)
                else:
                    response_body = str(data)
                
                self.send_header('Content-Length', str(len(response_body.encode('utf-8'))))
                self.end_headers()
                
                self.wfile.write(response_body.encode('utf-8'))
            
            def _send_error_response(self, status_code: int, message: str) -> None:
                """Envia resposta de erro"""
                error_data = {
                    'error': {
                        'code': status_code,
                        'message': message,
                        'timestamp': time.time()
                    }
                }
                self._send_response(status_code, error_data)
            
            def do_GET(self):
                """Processa requisições GET"""
                try:
                    parsed_url = urlparse(self.path)
                    path = parsed_url.path
                    query_params = parse_qs(parsed_url.query)
                    
                    # Remove listas de um elemento dos query params
                    query_params = {k: v[0] if len(v) == 1 else v 
                                  for k, v in query_params.items()}
                    
                    # Log da requisição
                    with self.endpoints.logger.context(component='monitoring_endpoints', operation='http_request'):
                        self.endpoints.logger.info(f"HTTP GET {path}", {
                            'http_method': 'GET',
                            'http_path': path,
                            'query_params': query_params,
                            'remote_addr': self.client_address[0]
                        })
                        
                        # Roteamento
                        if path == '/health':
                            self._handle_health(query_params)
                        elif path == '/health/live':
                            self._handle_liveness(query_params)
                        elif path == '/health/ready':
                            self._handle_readiness(query_params)
                        elif path == '/metrics':
                            self._handle_metrics(query_params)
                        elif path == '/status':
                            self._handle_status(query_params)
                        elif path in self.endpoints.custom_handlers:
                            self._handle_custom(path, query_params)
                        else:
                            self._handle_not_found()
                
                except Exception as e:
                    self.endpoints.logger.error("Error processing request", exception=e)
                    self._send_error_response(500, "Internal server error")
            
            def do_OPTIONS(self):
                """Processa requisições OPTIONS (CORS preflight)"""
                if self.endpoints.cors_enabled:
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                else:
                    self.send_response(405)
                    self.end_headers()
            
            def _handle_health(self, query_params: Dict[str, Any]) -> None:
                """Endpoint de health check geral"""
                try:
                    # Executa health checks
                    health_results = self.endpoints.health_checker.run_all_checks()
                    overall_status = self.endpoints.health_checker.get_overall_status()
                    
                    # Determina status HTTP
                    status_code = 200 if overall_status.value == 'healthy' else 503
                    
                    response_data = {
                        'status': overall_status.value,
                        'timestamp': time.time(),
                        'checks': {
                            name: {
                                'status': result.status.value,
                                'message': result.message,
                                'duration_ms': result.duration_ms
                            }
                            for name, result in health_results.items()
                        }
                    }
                    
                    self._send_response(status_code, response_data)
                
                except Exception as e:
                    self.endpoints.logger.error("Health check failed", exception=e)
                    self._send_error_response(500, "Health check failed")
            
            def _handle_liveness(self, query_params: Dict[str, Any]) -> None:
                """Endpoint de liveness probe (Kubernetes)"""
                # Liveness é sempre OK se o processo está rodando
                response_data = {
                    'status': 'alive',
                    'timestamp': time.time(),
                    'uptime_seconds': time.time() - self.endpoints.metrics_collector.start_time
                }
                
                self._send_response(200, response_data)
            
            def _handle_readiness(self, query_params: Dict[str, Any]) -> None:
                """Endpoint de readiness probe (Kubernetes)"""
                try:
                    # Executa readiness checks
                    readiness_results = self.endpoints.readiness_checker.run_all_checks()
                    is_ready = self.endpoints.readiness_checker.is_ready()
                    
                    status_code = 200 if is_ready else 503
                    
                    response_data = {
                        'status': 'ready' if is_ready else 'not_ready',
                        'timestamp': time.time(),
                        'checks': {
                            name: {
                                'status': result.status.value,
                                'message': result.message,
                                'duration_ms': result.duration_ms
                            }
                            for name, result in readiness_results.items()
                        }
                    }
                    
                    self._send_response(status_code, response_data)
                
                except Exception as e:
                    self.endpoints.logger.error("Readiness check failed", exception=e)
                    self._send_error_response(500, "Readiness check failed")
            
            def _handle_metrics(self, query_params: Dict[str, Any]) -> None:
                """Endpoint de métricas (formato Prometheus)"""
                try:
                    format_type = query_params.get('format', 'prometheus')
                    
                    if format_type == 'json':
                        # Formato JSON
                        metrics_data = self.endpoints.metrics_collector.get_metrics_summary()
                        self._send_response(200, metrics_data)
                    else:
                        # Formato Prometheus (padrão)
                        prometheus_data = self.endpoints.metrics_collector.export_prometheus()
                        self._send_response(200, prometheus_data, 'text/plain; charset=utf-8')
                
                except Exception as e:
                    self.endpoints.logger.error("Metrics export failed", exception=e)
                    self._send_error_response(500, "Metrics export failed")
            
            def _handle_status(self, query_params: Dict[str, Any]) -> None:
                """Endpoint de status detalhado"""
                try:
                    include_metrics = query_params.get('metrics', 'true').lower() == 'true'
                    include_health = query_params.get('health', 'true').lower() == 'true'
                    include_system = query_params.get('system', 'true').lower() == 'true'
                    
                    response_data = {
                        'timestamp': time.time(),
                        'uptime_seconds': time.time() - self.endpoints.metrics_collector.start_time,
                        'version': '1.0.0',  # TODO: Obter da configuração
                        'environment': 'development'  # TODO: Obter da configuração
                    }
                    
                    if include_health:
                        health_summary = self.endpoints.health_checker.get_health_summary()
                        readiness_summary = self.endpoints.readiness_checker.get_readiness_summary()
                        
                        response_data['health'] = health_summary
                        response_data['readiness'] = readiness_summary
                    
                    if include_metrics:
                        metrics_summary = self.endpoints.metrics_collector.get_metrics_summary()
                        response_data['metrics'] = metrics_summary
                    
                    if include_system and self.endpoints.enable_system_info:
                        import psutil
                        import platform
                        
                        response_data['system'] = {
                            'platform': platform.platform(),
                            'python_version': platform.python_version(),
                            'cpu_count': psutil.cpu_count(),
                            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                            'disk_total_gb': psutil.disk_usage('/').total / (1024**3)
                        }
                    
                    self._send_response(200, response_data)
                
                except Exception as e:
                    self.endpoints.logger.error("Status endpoint failed", exception=e)
                    self._send_error_response(500, "Status endpoint failed")
            
            def _handle_custom(self, path: str, query_params: Dict[str, Any]) -> None:
                """Processa handlers personalizados"""
                try:
                    handler = self.endpoints.custom_handlers[path]
                    status_code, response_data = handler(query_params)
                    self._send_response(status_code, response_data)
                
                except Exception as e:
                    self.endpoints.logger.error(f"Custom handler failed for {path}", exception=e)
                    self._send_error_response(500, "Custom handler failed")
            
            def _handle_not_found(self) -> None:
                """Endpoint não encontrado"""
                available_endpoints = [
                    '/health',
                    '/health/live',
                    '/health/ready',
                    '/metrics',
                    '/status'
                ] + list(self.endpoints.custom_handlers.keys())
                
                response_data = {
                    'error': {
                        'code': 404,
                        'message': 'Endpoint not found',
                        'available_endpoints': available_endpoints
                    }
                }
                
                self._send_response(404, response_data)
        
        # Cria e inicia o servidor
        try:
            self.server = HTTPServer((self.host, self.port), MonitoringHandler)
            self.running = True
            
            # Inicia health checks em background
            self.health_checker.start_background_checks()
            
            # Thread para o servidor
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"Monitoring endpoints started on {self.host}:{self.port}", {
                'host': self.host,
                'port': self.port,
                'endpoints': [
                    '/health',
                    '/health/live', 
                    '/health/ready',
                    '/metrics',
                    '/status'
                ]
            })
        
        except Exception as e:
            self.logger.error("Failed to start monitoring endpoints", exception=e)
            raise
    
    def stop(self) -> None:
        """Para o servidor de endpoints"""
        if not self.running:
            return
        
        self.running = False
        
        # Para health checks
        self.health_checker.stop_background_checks()
        
        # Para o servidor
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        # Aguarda thread terminar
        if self.server_thread:
            self.server_thread.join(timeout=5)
        
        self.logger.info("Monitoring endpoints stopped")
    
    def is_running(self) -> bool:
        """Verifica se o servidor está rodando"""
        return self.running
    
    def get_url(self, endpoint: str = '') -> str:
        """Retorna URL completa para um endpoint"""
        base_url = f"http://{self.host}:{self.port}"
        if endpoint and not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        return base_url + endpoint