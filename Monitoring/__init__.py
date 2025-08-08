"""PySocketCommLib Monitoring System

Sistema completo de monitoramento, métricas e observabilidade para PySocketCommLib.
Inclui coleta de métricas de performance, health checks, logs estruturados e endpoints de monitoramento.

Módulos:
- metrics: Coleta e armazenamento de métricas de performance
- health: Verificações de saúde e prontidão do sistema
- logging: Sistema de logs estruturados em JSON
- endpoints: Endpoints HTTP para exposição de métricas e health checks

Exemplo de uso:
    from Monitoring import MetricsCollector, HealthChecker
    
    # Inicializar coleta de métricas
    metrics = MetricsCollector()
    metrics.start_collection()
    
    # Verificar saúde do sistema
    health = HealthChecker()
    status = await health.check_all()
"""

from .metrics.collector import MetricsCollector
from .metrics.performance import PerformanceTracker
from .metrics.connection_monitor import ConnectionMonitor
from .health.checker import HealthChecker
from .health.readiness import ReadinessChecker
from .log_utils.structured_logger import StructuredLogger
from .endpoints.health_endpoints import HealthEndpoints

__version__ = "1.0.0"
__all__ = [
    "MetricsCollector",
    "PerformanceTracker", 
    "ConnectionMonitor",
    "HealthChecker",
    "ReadinessChecker",
    "StructuredLogger",
    "HealthEndpoints"
]