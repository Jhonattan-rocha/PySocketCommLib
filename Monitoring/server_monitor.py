"""
ServerMonitor — ponte entre os servidores da biblioteca e o sistema de monitoramento.

Conecta os eventos de lifecycle dos servidores (socket e HTTP) ao
MetricsCollector e ConnectionMonitor, e expõe os endpoints /metrics,
/health e /connections no HTTP server.

Uso básico:
    from PySocketCommLib import AsyncServer, AsyncHttpServerProtocol
    from PySocketCommLib.Monitoring import ServerMonitor

    monitor = ServerMonitor()

    # servidor socket
    server = AsyncServer(options)
    monitor.attach_to_server(server)

    # servidor HTTP
    http = AsyncHttpServerProtocol(...)
    monitor.attach_to_http_server(http)
    monitor.add_http_endpoints(http)
    monitor.start()
"""
import json
import time
import logging
from typing import Optional

from .metrics.collector import MetricsCollector
from .metrics.connection_monitor import ConnectionMonitor, ConnectionType, ConnectionState
from .health.checker import HealthChecker

logger = logging.getLogger(__name__)


class ServerMonitor:
    """
    Integra MetricsCollector, ConnectionMonitor e HealthChecker aos servidores.

    Um único monitor pode ser conectado a múltiplos servidores (socket e HTTP).
    """

    def __init__(
        self,
        metrics: Optional[MetricsCollector] = None,
        connection_monitor: Optional[ConnectionMonitor] = None,
        health_checker: Optional[HealthChecker] = None,
    ) -> None:
        self.metrics = metrics or MetricsCollector()
        self.conn_monitor = connection_monitor or ConnectionMonitor(self.metrics)
        self.health_checker = health_checker or HealthChecker()

    def start(self, metrics_interval: float = 5.0, health_interval: int = 30) -> None:
        """Inicia coleta automática de métricas e health checks em background."""
        self.metrics.start_collection(interval=metrics_interval)
        self.conn_monitor.start_monitoring()
        self.health_checker.start_background_checks(interval=health_interval)
        logger.info("ServerMonitor iniciado.")

    def stop(self) -> None:
        """Para a coleta em background."""
        self.metrics.stop_collection()
        self.conn_monitor.stop_monitoring()
        self.health_checker.stop_background_checks()
        logger.info("ServerMonitor parado.")

    # ------------------------------------------------------------------
    # Integração com servidores socket (AsyncServer / ThreadServer)
    # ------------------------------------------------------------------

    def attach_to_server(self, server) -> None:
        """
        Conecta ao servidor socket para monitorar conexões via eventos de lifecycle.

        O servidor deve emitir:
            server.connect(uuid, address)
            server.disconnect(uuid, address)   (apenas AsyncServer)
        """
        server.events.on("server.connect", self._on_socket_connect)
        server.events.on("server.disconnect", self._on_socket_disconnect)
        logger.info(f"ServerMonitor conectado ao servidor socket: {server}")

    def _on_socket_connect(self, uuid: str, address) -> None:
        remote_host = address[0] if address else "unknown"
        remote_port = address[1] if address and len(address) > 1 else 0
        self.conn_monitor.register_connection(
            connection_id=uuid,
            connection_type=ConnectionType.TCP,
            local_address="",
            local_port=0,
            remote_address=remote_host,
            remote_port=remote_port,
        )
        self.conn_monitor.update_connection_state(uuid, ConnectionState.CONNECTED)
        self.metrics.increment_counter("socket_connections_total")

    def _on_socket_disconnect(self, uuid: str, address) -> None:
        self.conn_monitor.update_connection_state(uuid, ConnectionState.DISCONNECTED)
        self.metrics.increment_counter("socket_disconnections_total")

    # ------------------------------------------------------------------
    # Integração com HTTP server (AsyncHttpServerProtocol)
    # ------------------------------------------------------------------

    def attach_to_http_server(self, http_server) -> None:
        """
        Conecta ao HTTP server para coletar métricas via eventos de lifecycle.

        Requer que o servidor já emita:
            http.request(method, path)
            http.response(method, path, status)
            http.error(method, path, error)
        """
        http_server.on("http.request", self._on_http_request)
        http_server.on("http.response", self._on_http_response)
        http_server.on("http.error", self._on_http_error)
        logger.info("ServerMonitor conectado ao HTTP server.")

    def _on_http_request(self, method: str, path: str) -> None:
        self.metrics.increment_counter(
            "http_requests_total",
            labels={"method": method, "path": path},
        )

    def _on_http_response(self, method: str, path: str, status: int = 200) -> None:
        self.metrics.increment_counter(
            "http_responses_total",
            labels={"method": method, "status": str(status)},
        )
        self.metrics.record_histogram(
            "http_response_status",
            float(status),
            labels={"method": method},
        )

    def _on_http_error(self, method: str, path: str, error: str = "") -> None:
        self.metrics.increment_counter(
            "http_errors_total",
            labels={"method": method, "path": path},
        )

    # ------------------------------------------------------------------
    # Endpoints HTTP: /metrics, /health, /connections
    # ------------------------------------------------------------------

    def add_http_endpoints(self, http_server) -> None:
        """
        Registra /metrics, /health e /connections no HTTP server.

        Deve ser chamado após attach_to_http_server (mas não é obrigatório).
        """
        monitor = self  # captura para closures

        @http_server.get("/metrics")
        def metrics_endpoint(params):
            from ..Protocols.protocols.httpServer.Responses.JSONResponse import JSONResponse
            data = monitor.metrics.get_metrics_summary()
            return JSONResponse(data)

        @http_server.get("/health")
        def health_endpoint(params):
            from ..Protocols.protocols.httpServer.Responses.JSONResponse import JSONResponse
            monitor.health_checker.run_all_checks()
            summary = monitor.health_checker.get_health_summary()
            status_code = 200 if summary.get("status") == "healthy" else 503
            return JSONResponse(summary, status=status_code)

        @http_server.get("/connections")
        def connections_endpoint(params):
            from ..Protocols.protocols.httpServer.Responses.JSONResponse import JSONResponse
            data = monitor.conn_monitor.export_connections_data()
            return JSONResponse(data)

        logger.info("Endpoints /metrics, /health e /connections registrados.")
