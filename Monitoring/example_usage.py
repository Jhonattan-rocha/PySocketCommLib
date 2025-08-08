"""Example Usage of Monitoring System

Exemplo de como usar o sistema de monitoramento completo:
- Configuração de métricas
- Health checks personalizados
- Logging estruturado
- Endpoints HTTP
"""

import time
import asyncio
from typing import Dict, Any

# Imports do sistema de monitoramento
from Monitoring.metrics.collector import MetricsCollector
from Monitoring.metrics.performance import PerformanceTracker
from Monitoring.metrics.connection_monitor import ConnectionMonitor
from Monitoring.health.checker import HealthChecker, HealthStatus, HealthCheckResult
from Monitoring.health.readiness import ReadinessChecker
from Monitoring.log_utils.structured_logger import StructuredLogger
from Monitoring.endpoints.health_endpoints import HealthEndpoints


class MonitoringExample:
    """Exemplo de uso do sistema de monitoramento"""
    
    def __init__(self):
        # Inicializa componentes
        self.metrics = MetricsCollector()
        self.performance = PerformanceTracker()
        self.connection_monitor = ConnectionMonitor()
        self.health_checker = HealthChecker()
        self.readiness_checker = ReadinessChecker()
        self.endpoints = HealthEndpoints(host='localhost', port=8888)
        
        # Configura logging
        self.logger = StructuredLogger()
        self.logger.configure(level='INFO')
        self.logger.set_metrics_integration(self.metrics)
        
        # Registra health checks personalizados
        self._setup_custom_health_checks()
        
        # Configura dependências de readiness
        self._setup_readiness_dependencies()
    
    def _setup_custom_health_checks(self):
        """Configura health checks personalizados"""
        
        def check_database_connection() -> HealthCheckResult:
            """Simula verificação de conexão com banco"""
            try:
                # Simula verificação de banco de dados
                time.sleep(0.1)  # Simula latência
                
                # Simula sucesso/falha baseado no tempo
                import random
                if random.random() > 0.1:  # 90% de sucesso
                    return HealthCheckResult(
                        name="database_connection",
                        status=HealthStatus.HEALTHY,
                        message="Database connection is healthy",
                        duration_ms=100,
                        timestamp=time.time(),
                        details={
                            "connection_pool_size": 10,
                            "active_connections": 3,
                            "query_response_time_ms": 50
                        }
                    )
                else:
                    return HealthCheckResult(
                        name="database_connection",
                        status=HealthStatus.UNHEALTHY,
                        message="Database connection failed",
                        duration_ms=100,
                        timestamp=time.time()
                    )
            except Exception as e:
                return HealthCheckResult(
                    name="database_connection",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database check error: {str(e)}",
                    duration_ms=100,
                    timestamp=time.time()
                )
        
        def check_cache_service() -> HealthCheckResult:
            """Simula verificação de serviço de cache"""
            try:
                # Simula verificação de Redis/Memcached
                cache_hit_rate = 0.85  # 85% hit rate
                
                if cache_hit_rate > 0.7:
                    status = HealthStatus.HEALTHY
                    message = f"Cache service healthy (hit rate: {cache_hit_rate:.1%})"
                elif cache_hit_rate > 0.5:
                    status = HealthStatus.DEGRADED
                    message = f"Cache service degraded (hit rate: {cache_hit_rate:.1%})"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"Cache service unhealthy (hit rate: {cache_hit_rate:.1%})"
                
                return HealthCheckResult(
                    name="cache_service",
                    status=status,
                    message=message,
                    duration_ms=25,
                    timestamp=time.time(),
                    details={
                        "hit_rate": cache_hit_rate,
                        "memory_usage_mb": 256,
                        "connected_clients": 15
                    }
                )
            except Exception as e:
                return HealthCheckResult(
                    name="cache_service",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Cache check error: {str(e)}",
                    duration_ms=25,
                    timestamp=time.time()
                )
        
        # Registra os health checks
        self.health_checker.register_check("database_connection", check_database_connection)
        self.health_checker.register_check("cache_service", check_cache_service)
    
    def _setup_readiness_dependencies(self):
        """Configura dependências de readiness"""
        # Dependência de banco de dados
        self.readiness_checker.add_database_dependency(
            name="main_db",
            host="localhost",
            port=5432,
            database="app_db",
            timeout=5
        )
        
        # Dependência HTTP (API externa)
        self.readiness_checker.add_http_dependency(
            name="external_api",
            url="https://httpbin.org/status/200",
            expected_status=200,
            timeout=10
        )
        
        # Dependência TCP (Redis)
        self.readiness_checker.add_tcp_dependency(
            name="redis",
            host="localhost",
            port=6379,
            timeout=3
        )
    
    def start_monitoring(self):
        """Inicia o sistema de monitoramento"""
        with self.logger.context(component='monitoring_system', operation='startup'):
            self.logger.info("Starting monitoring system")
            
            try:
                # Inicia endpoints HTTP
                self.endpoints.start()
                
                # Inicia monitoramento de conexões
                self.connection_monitor.start_monitoring()
                
                self.logger.info("Monitoring system started successfully", {
                    'endpoints_url': self.endpoints.get_url(),
                    'health_url': self.endpoints.get_url('/health'),
                    'metrics_url': self.endpoints.get_url('/metrics')
                })
                
            except Exception as e:
                self.logger.error("Failed to start monitoring system", exception=e)
                raise
    
    def stop_monitoring(self):
        """Para o sistema de monitoramento"""
        with self.logger.context(component='monitoring_system', operation='shutdown'):
            self.logger.info("Stopping monitoring system")
            
            try:
                # Para endpoints
                self.endpoints.stop()
                
                # Para monitoramento de conexões
                self.connection_monitor.stop_monitoring()
                
                self.logger.info("Monitoring system stopped successfully")
                
            except Exception as e:
                self.logger.error("Error stopping monitoring system", exception=e)
    
    def simulate_business_operation(self, operation_name: str, duration: float = 1.0):
        """Simula uma operação de negócio com tracking de performance"""
        with self.performance.measure_time(operation_name):
            with self.logger.context(operation=operation_name):
                self.logger.info(f"Starting {operation_name}")
                
                # Simula trabalho
                time.sleep(duration)
                
                # Registra métricas
                self.metrics.increment_counter(f'business.{operation_name}.completed')
                self.metrics.record_histogram(f'business.{operation_name}.duration', duration * 1000)
                
                self.logger.info(f"Completed {operation_name}", {
                    'operation_duration_ms': duration * 1000
                })
    
    async def simulate_async_operation(self, operation_name: str, duration: float = 0.5):
        """Simula operação assíncrona com tracking"""
        async with self.performance.measure_time_async(f'async_{operation_name}'):
            with self.logger.context(operation=f'async_{operation_name}'):
                self.logger.info(f"Starting async {operation_name}")
                
                # Simula trabalho assíncrono
                await asyncio.sleep(duration)
                
                # Registra métricas
                self.metrics.increment_counter(f'async.{operation_name}.completed')
                
                self.logger.info(f"Completed async {operation_name}")
    
    def simulate_database_operations(self):
        """Simula operações de banco de dados"""
        operations = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']
        
        for operation in operations:
            start_time = time.time()
            
            # Simula query
            query_duration = 0.05 + (0.1 * len(operation) / 10)  # Varia por operação
            time.sleep(query_duration)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Log estruturado da query
            self.logger.log_database_query(
                query=f"{operation} * FROM users WHERE active = true",
                duration_ms=duration_ms,
                rows_affected=10 if operation != 'SELECT' else None
            )
            
            # Métricas de banco
            self.metrics.increment_counter(f'database.queries.{operation.lower()}')
            self.metrics.record_histogram('database.query_duration', duration_ms)
    
    def simulate_cache_operations(self):
        """Simula operações de cache"""
        cache_keys = ['user:123', 'session:abc', 'config:app', 'data:xyz']
        
        for key in cache_keys:
            # Simula operação de cache
            import random
            hit = random.random() > 0.3  # 70% hit rate
            operation = 'GET'
            duration_ms = 5 if hit else 50  # Cache hit é mais rápido
            
            time.sleep(duration_ms / 1000)
            
            # Log de cache
            self.logger.log_cache_operation(
                operation=operation,
                key=key,
                hit=hit,
                duration_ms=duration_ms
            )
            
            # Métricas de cache
            self.metrics.increment_counter(f'cache.{operation.lower()}.{"hit" if hit else "miss"}')
            self.metrics.record_histogram('cache.operation_duration', duration_ms)
    
    def simulate_http_requests(self):
        """Simula requisições HTTP"""
        endpoints = [
            ('/api/users', 'GET', 200),
            ('/api/users', 'POST', 201),
            ('/api/users/123', 'GET', 200),
            ('/api/users/999', 'GET', 404),
            ('/api/health', 'GET', 200)
        ]
        
        for path, method, status_code in endpoints:
            # Simula request
            request_context = self.logger.log_request_start(
                method=method,
                path=path,
                user_id='user_123'
            )
            
            # Simula processamento
            processing_time = 0.1 + (0.05 * len(path) / 10)
            time.sleep(processing_time)
            
            duration_ms = processing_time * 1000
            response_size = 1024 if status_code < 400 else 256
            
            # Log de fim do request
            self.logger.log_request_end(
                status_code=status_code,
                duration_ms=duration_ms,
                response_size=response_size
            )
            
            # Métricas HTTP
            self.metrics.increment_counter(f'http.requests.{method.lower()}')
            self.metrics.increment_counter(f'http.responses.{status_code}')
            self.metrics.record_histogram('http.request_duration', duration_ms)
    
    def run_demo(self, duration: int = 60):
        """Executa demonstração do sistema de monitoramento"""
        print(f"\n🚀 Iniciando demonstração do sistema de monitoramento por {duration} segundos...")
        print(f"📊 Endpoints disponíveis:")
        print(f"   - Health: {self.endpoints.get_url('/health')}")
        print(f"   - Readiness: {self.endpoints.get_url('/health/ready')}")
        print(f"   - Metrics: {self.endpoints.get_url('/metrics')}")
        print(f"   - Status: {self.endpoints.get_url('/status')}")
        print(f"\n💡 Acesse os endpoints no seu navegador para ver os dados!\n")
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                # Simula diferentes tipos de operações
                self.simulate_business_operation("user_registration", 0.2)
                self.simulate_database_operations()
                self.simulate_cache_operations()
                self.simulate_http_requests()
                
                # Operação assíncrona
                asyncio.run(self.simulate_async_operation("email_sending", 0.3))
                
                # Aguarda antes da próxima iteração
                time.sleep(2)
                
                # Mostra progresso
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                print(f"⏱️  Tempo restante: {remaining:.0f}s - Operações simuladas em andamento...")
        
        except KeyboardInterrupt:
            print("\n⏹️  Demonstração interrompida pelo usuário")
        
        print("\n✅ Demonstração concluída!")
        print("📈 Verifique os endpoints para ver as métricas coletadas.")


def main():
    """Função principal para executar o exemplo"""
    example = MonitoringExample()
    
    try:
        # Inicia o sistema de monitoramento
        example.start_monitoring()
        
        # Executa demonstração
        example.run_demo(duration=120)  # 2 minutos
        
    except KeyboardInterrupt:
        print("\n⏹️  Parando sistema de monitoramento...")
    
    finally:
        # Para o sistema
        example.stop_monitoring()
        print("🏁 Sistema de monitoramento parado.")


if __name__ == "__main__":
    main()