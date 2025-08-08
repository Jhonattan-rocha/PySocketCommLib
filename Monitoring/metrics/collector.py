"""Metrics Collector

Coletor centralizado de métricas de performance para PySocketCommLib.
Implementa padrão singleton para garantir coleta unificada em toda a aplicação.
"""

import time
import threading
import psutil
from collections import defaultdict, deque
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json


@dataclass
class MetricPoint:
    """Representa um ponto de métrica com timestamp."""
    timestamp: float
    value: float
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


class MetricsCollector:
    """Coletor centralizado de métricas com padrão singleton."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        
        self._collection_thread: Optional[threading.Thread] = None
        self._stop_collection = threading.Event()
        self._collection_interval = 5.0  # segundos
        
        self._start_time = time.time()
        
    def start_collection(self, interval: float = 5.0) -> None:
        """Inicia a coleta automática de métricas do sistema.
        
        Args:
            interval: Intervalo de coleta em segundos
        """
        if self._collection_thread and self._collection_thread.is_alive():
            return
            
        self._collection_interval = interval
        self._stop_collection.clear()
        
        self._collection_thread = threading.Thread(
            target=self._collect_system_metrics,
            daemon=True
        )
        self._collection_thread.start()
        
    def stop_collection(self) -> None:
        """Para a coleta automática de métricas."""
        self._stop_collection.set()
        if self._collection_thread:
            self._collection_thread.join(timeout=1.0)
            
    def _collect_system_metrics(self) -> None:
        """Coleta métricas do sistema em thread separada."""
        while not self._stop_collection.wait(self._collection_interval):
            try:
                # Métricas de CPU
                cpu_percent = psutil.cpu_percent(interval=None)
                self.record_gauge('system_cpu_percent', cpu_percent)
                
                # Métricas de memória
                memory = psutil.virtual_memory()
                self.record_gauge('system_memory_percent', memory.percent)
                self.record_gauge('system_memory_used_bytes', memory.used)
                self.record_gauge('system_memory_available_bytes', memory.available)
                
                # Métricas de disco
                disk = psutil.disk_usage('/')
                self.record_gauge('system_disk_percent', disk.percent)
                self.record_gauge('system_disk_used_bytes', disk.used)
                self.record_gauge('system_disk_free_bytes', disk.free)
                
                # Uptime
                uptime = time.time() - self._start_time
                self.record_gauge('system_uptime_seconds', uptime)
                
            except Exception as e:
                # Log error but continue collection
                print(f"Error collecting system metrics: {e}")
                
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None) -> None:
        """Incrementa um contador.
        
        Args:
            name: Nome da métrica
            value: Valor a incrementar
            labels: Labels opcionais
        """
        key = self._build_metric_key(name, labels)
        self._counters[key] += value
        
        # Também armazena como série temporal
        metric_point = MetricPoint(
            timestamp=time.time(),
            value=self._counters[key],
            labels=labels or {}
        )
        self._metrics[key].append(metric_point)
        
    def record_gauge(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """Registra um valor de gauge.
        
        Args:
            name: Nome da métrica
            value: Valor atual
            labels: Labels opcionais
        """
        key = self._build_metric_key(name, labels)
        self._gauges[key] = value
        
        metric_point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        self._metrics[key].append(metric_point)
        
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """Registra um valor em histograma.
        
        Args:
            name: Nome da métrica
            value: Valor a registrar
            labels: Labels opcionais
        """
        key = self._build_metric_key(name, labels)
        self._histograms[key].append(value)
        
        # Manter apenas últimos 1000 valores
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]
            
        metric_point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        self._metrics[key].append(metric_point)
        
    def get_counter(self, name: str, labels: Dict[str, str] = None) -> int:
        """Obtém valor atual de um contador."""
        key = self._build_metric_key(name, labels)
        return self._counters.get(key, 0)
        
    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Obtém valor atual de um gauge."""
        key = self._build_metric_key(name, labels)
        return self._gauges.get(key, 0.0)
        
    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Obtém estatísticas de um histograma."""
        key = self._build_metric_key(name, labels)
        values = self._histograms.get(key, [])
        
        if not values:
            return {'count': 0, 'sum': 0, 'avg': 0, 'min': 0, 'max': 0}
            
        return {
            'count': len(values),
            'sum': sum(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values)
        }
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Obtém resumo de todas as métricas."""
        summary = {
            'timestamp': time.time(),
            'uptime_seconds': time.time() - self._start_time,
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'histograms': {}
        }
        
        for name in self._histograms:
            summary['histograms'][name] = self.get_histogram_stats(name)
            
        return summary
        
    def get_metrics_prometheus_format(self) -> str:
        """Exporta métricas no formato Prometheus."""
        lines = []
        
        # Counters
        for key, value in self._counters.items():
            lines.append(f"{key} {value}")
            
        # Gauges
        for key, value in self._gauges.items():
            lines.append(f"{key} {value}")
            
        # Histograms (simplified)
        for key in self._histograms:
            stats = self.get_histogram_stats(key)
            lines.append(f"{key}_count {stats['count']}")
            lines.append(f"{key}_sum {stats['sum']}")
            
        return '\n'.join(lines)
        
    def get_time_series(self, name: str, labels: Dict[str, str] = None, 
                       duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """Obtém série temporal de uma métrica.
        
        Args:
            name: Nome da métrica
            labels: Labels opcionais
            duration_minutes: Duração em minutos
            
        Returns:
            Lista de pontos da série temporal
        """
        key = self._build_metric_key(name, labels)
        metrics = self._metrics.get(key, deque())
        
        cutoff_time = time.time() - (duration_minutes * 60)
        
        return [
            asdict(point) for point in metrics 
            if point.timestamp >= cutoff_time
        ]
        
    def _build_metric_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Constrói chave única para métrica com labels."""
        if not labels:
            return name
            
        label_str = ','.join(f'{k}={v}' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
        
    def reset_metrics(self) -> None:
        """Reseta todas as métricas."""
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.time()
        
    def export_to_json(self, filepath: str) -> None:
        """Exporta métricas para arquivo JSON."""
        data = {
            'export_timestamp': time.time(),
            'metrics_summary': self.get_metrics_summary(),
            'time_series': {}
        }
        
        # Exportar séries temporais das principais métricas
        for key in list(self._metrics.keys())[:50]:  # Limitar a 50 métricas
            data['time_series'][key] = [
                asdict(point) for point in list(self._metrics[key])[-100:]  # Últimos 100 pontos
            ]
            
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)