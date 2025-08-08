"""Monitoring Endpoints Module

Módulo responsável por endpoints HTTP para monitoramento.
Inclui endpoints para health checks, métricas e status do sistema.
"""

from .health_endpoints import HealthEndpoints

__all__ = ["HealthEndpoints"]