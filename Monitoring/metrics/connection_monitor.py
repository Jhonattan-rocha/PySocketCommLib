"""Connection Monitor

Monitor de conexões ativas, estatísticas de rede e uso de recursos de conexão.
Rastreia conexões TCP/UDP, WebSocket, e outras conexões de rede.
"""

import time
import threading
import socket
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
from .collector import MetricsCollector


class ConnectionType(Enum):
    """Tipos de conexão suportados."""
    TCP = "tcp"
    UDP = "udp"
    WEBSOCKET = "websocket"
    HTTP = "http"
    HTTPS = "https"
    UNKNOWN = "unknown"


class ConnectionState(Enum):
    """Estados de conexão."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """Informações de uma conexão."""
    connection_id: str
    connection_type: ConnectionType
    state: ConnectionState
    local_address: str
    local_port: int
    remote_address: Optional[str] = None
    remote_port: Optional[int] = None
    created_at: float = None
    last_activity: float = None
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_activity is None:
            self.last_activity = time.time()
        if self.metadata is None:
            self.metadata = {}
            
    @property
    def duration_seconds(self) -> float:
        """Duração da conexão em segundos."""
        return time.time() - self.created_at
        
    @property
    def idle_seconds(self) -> float:
        """Tempo inativo em segundos."""
        return time.time() - self.last_activity


class ConnectionMonitor:
    """Monitor de conexões com coleta automática de métricas."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        
        # Armazenamento de conexões
        self._connections: Dict[str, ConnectionInfo] = {}
        self._connection_history: deque = deque(maxlen=10000)
        
        # Estatísticas por tipo
        self._stats_by_type: Dict[ConnectionType, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        
        # Lock para thread safety
        self._lock = threading.RLock()
        
        # Thread de limpeza
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        # Configurações
        self.idle_timeout_seconds = 300  # 5 minutos
        self.cleanup_interval_seconds = 60  # 1 minuto
        
    def start_monitoring(self) -> None:
        """Inicia o monitoramento automático."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
            
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_connections,
            daemon=True
        )
        self._cleanup_thread.start()
        
    def stop_monitoring(self) -> None:
        """Para o monitoramento automático."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1.0)
            
    def register_connection(self, connection_id: str, 
                          connection_type: ConnectionType,
                          local_address: str, local_port: int,
                          remote_address: Optional[str] = None,
                          remote_port: Optional[int] = None,
                          metadata: Dict[str, Any] = None) -> None:
        """Registra uma nova conexão.
        
        Args:
            connection_id: ID único da conexão
            connection_type: Tipo da conexão
            local_address: Endereço local
            local_port: Porta local
            remote_address: Endereço remoto (opcional)
            remote_port: Porta remota (opcional)
            metadata: Metadados adicionais
        """
        with self._lock:
            connection = ConnectionInfo(
                connection_id=connection_id,
                connection_type=connection_type,
                state=ConnectionState.CONNECTING,
                local_address=local_address,
                local_port=local_port,
                remote_address=remote_address,
                remote_port=remote_port,
                metadata=metadata or {}
            )
            
            self._connections[connection_id] = connection
            
            # Atualizar métricas
            self._update_connection_metrics()
            
            # Incrementar contador
            labels = {'type': connection_type.value, 'state': 'connecting'}
            self.metrics_collector.increment_counter('connections_total', labels=labels)
            
    def update_connection_state(self, connection_id: str, 
                              state: ConnectionState) -> None:
        """Atualiza o estado de uma conexão.
        
        Args:
            connection_id: ID da conexão
            state: Novo estado
        """
        with self._lock:
            if connection_id not in self._connections:
                return
                
            connection = self._connections[connection_id]
            old_state = connection.state
            connection.state = state
            connection.last_activity = time.time()
            
            # Se desconectou, mover para histórico
            if state == ConnectionState.DISCONNECTED:
                self._connection_history.append(connection)
                del self._connections[connection_id]
                
            # Atualizar métricas
            self._update_connection_metrics()
            
            # Registrar mudança de estado
            labels = {
                'type': connection.connection_type.value,
                'from_state': old_state.value,
                'to_state': state.value
            }
            self.metrics_collector.increment_counter(
                'connection_state_changes_total', 
                labels=labels
            )
            
    def record_data_transfer(self, connection_id: str, 
                           bytes_sent: int = 0, bytes_received: int = 0,
                           messages_sent: int = 0, messages_received: int = 0) -> None:
        """Registra transferência de dados.
        
        Args:
            connection_id: ID da conexão
            bytes_sent: Bytes enviados
            bytes_received: Bytes recebidos
            messages_sent: Mensagens enviadas
            messages_received: Mensagens recebidas
        """
        with self._lock:
            if connection_id not in self._connections:
                return
                
            connection = self._connections[connection_id]
            connection.bytes_sent += bytes_sent
            connection.bytes_received += bytes_received
            connection.messages_sent += messages_sent
            connection.messages_received += messages_received
            connection.last_activity = time.time()
            
            # Registrar métricas de transferência
            conn_type = connection.connection_type.value
            
            if bytes_sent > 0:
                self.metrics_collector.record_histogram(
                    'connection_bytes_sent',
                    bytes_sent,
                    labels={'type': conn_type}
                )
                
            if bytes_received > 0:
                self.metrics_collector.record_histogram(
                    'connection_bytes_received',
                    bytes_received,
                    labels={'type': conn_type}
                )
                
            if messages_sent > 0:
                self.metrics_collector.increment_counter(
                    'connection_messages_sent_total',
                    messages_sent,
                    labels={'type': conn_type}
                )
                
            if messages_received > 0:
                self.metrics_collector.increment_counter(
                    'connection_messages_received_total',
                    messages_received,
                    labels={'type': conn_type}
                )
                
    def get_active_connections(self, connection_type: Optional[ConnectionType] = None) -> List[ConnectionInfo]:
        """Obtém lista de conexões ativas.
        
        Args:
            connection_type: Filtrar por tipo (opcional)
            
        Returns:
            Lista de conexões ativas
        """
        with self._lock:
            connections = list(self._connections.values())
            
            if connection_type:
                connections = [c for c in connections if c.connection_type == connection_type]
                
            return connections
            
    def get_connection_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas gerais de conexões."""
        with self._lock:
            active_connections = list(self._connections.values())
            
            stats = {
                'active_connections': len(active_connections),
                'total_connections_history': len(self._connection_history),
                'by_type': {},
                'by_state': {},
                'data_transfer': {
                    'total_bytes_sent': 0,
                    'total_bytes_received': 0,
                    'total_messages_sent': 0,
                    'total_messages_received': 0
                }
            }
            
            # Estatísticas por tipo e estado
            for connection in active_connections:
                conn_type = connection.connection_type.value
                conn_state = connection.state.value
                
                if conn_type not in stats['by_type']:
                    stats['by_type'][conn_type] = 0
                stats['by_type'][conn_type] += 1
                
                if conn_state not in stats['by_state']:
                    stats['by_state'][conn_state] = 0
                stats['by_state'][conn_state] += 1
                
                # Somar transferência de dados
                stats['data_transfer']['total_bytes_sent'] += connection.bytes_sent
                stats['data_transfer']['total_bytes_received'] += connection.bytes_received
                stats['data_transfer']['total_messages_sent'] += connection.messages_sent
                stats['data_transfer']['total_messages_received'] += connection.messages_received
                
            return stats
            
    def get_connection_details(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de uma conexão específica.
        
        Args:
            connection_id: ID da conexão
            
        Returns:
            Detalhes da conexão ou None se não encontrada
        """
        with self._lock:
            connection = self._connections.get(connection_id)
            if connection:
                return asdict(connection)
            return None
            
    def get_idle_connections(self, idle_threshold_seconds: Optional[int] = None) -> List[ConnectionInfo]:
        """Obtém conexões inativas.
        
        Args:
            idle_threshold_seconds: Limite de inatividade (usa padrão se None)
            
        Returns:
            Lista de conexões inativas
        """
        threshold = idle_threshold_seconds or self.idle_timeout_seconds
        current_time = time.time()
        
        with self._lock:
            idle_connections = [
                conn for conn in self._connections.values()
                if current_time - conn.last_activity > threshold
            ]
            
        return idle_connections
        
    def cleanup_idle_connections(self, idle_threshold_seconds: Optional[int] = None) -> int:
        """Remove conexões inativas.
        
        Args:
            idle_threshold_seconds: Limite de inatividade
            
        Returns:
            Número de conexões removidas
        """
        idle_connections = self.get_idle_connections(idle_threshold_seconds)
        
        for connection in idle_connections:
            self.update_connection_state(connection.connection_id, ConnectionState.DISCONNECTED)
            
        return len(idle_connections)
        
    def _update_connection_metrics(self) -> None:
        """Atualiza métricas de conexão no coletor."""
        stats = self.get_connection_stats()
        
        # Gauge de conexões ativas
        self.metrics_collector.record_gauge(
            'connections_active',
            stats['active_connections']
        )
        
        # Gauges por tipo
        for conn_type, count in stats['by_type'].items():
            self.metrics_collector.record_gauge(
                'connections_active_by_type',
                count,
                labels={'type': conn_type}
            )
            
        # Gauges por estado
        for state, count in stats['by_state'].items():
            self.metrics_collector.record_gauge(
                'connections_by_state',
                count,
                labels={'state': state}
            )
            
    def _cleanup_connections(self) -> None:
        """Thread de limpeza automática de conexões inativas."""
        while not self._stop_cleanup.wait(self.cleanup_interval_seconds):
            try:
                cleaned = self.cleanup_idle_connections()
                if cleaned > 0:
                    print(f"Cleaned up {cleaned} idle connections")
                    
            except Exception as e:
                print(f"Error during connection cleanup: {e}")
                
    def export_connections_data(self) -> Dict[str, Any]:
        """Exporta dados de conexões para análise."""
        with self._lock:
            return {
                'timestamp': time.time(),
                'active_connections': [asdict(conn) for conn in self._connections.values()],
                'connection_history': [asdict(conn) for conn in list(self._connection_history)[-100:]],
                'stats': self.get_connection_stats()
            }


# Instância global
connection_monitor = ConnectionMonitor()