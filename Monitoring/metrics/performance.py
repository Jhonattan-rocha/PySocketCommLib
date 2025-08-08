"""Performance Tracker

Sistema de rastreamento de performance com decorators e context managers.
Permite medição automática de latência, throughput e outras métricas de performance.
"""

import time
import functools
import asyncio
from typing import Dict, Any, Optional, Callable, Union
from contextlib import contextmanager, asynccontextmanager
from collections import defaultdict, deque
from dataclasses import dataclass
from .collector import MetricsCollector


@dataclass
class PerformanceMetrics:
    """Métricas de performance de uma operação."""
    operation_name: str
    duration_seconds: float
    start_time: float
    end_time: float
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PerformanceTracker:
    """Rastreador de performance com suporte a sync/async."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._operation_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._active_operations: Dict[str, float] = {}
        
    def track_performance(self, operation_name: str = None, 
                         include_args: bool = False,
                         track_errors: bool = True):
        """Decorator para rastreamento automático de performance.
        
        Args:
            operation_name: Nome da operação (usa nome da função se None)
            include_args: Se deve incluir argumentos nos metadados
            track_errors: Se deve rastrear erros
        """
        def decorator(func: Callable) -> Callable:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return await self._track_async_operation(
                        func, op_name, args, kwargs, include_args, track_errors
                    )
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    return self._track_sync_operation(
                        func, op_name, args, kwargs, include_args, track_errors
                    )
                return sync_wrapper
                
        return decorator
        
    def _track_sync_operation(self, func: Callable, op_name: str, 
                             args: tuple, kwargs: dict,
                             include_args: bool, track_errors: bool) -> Any:
        """Rastreia operação síncrona."""
        start_time = time.time()
        metadata = {}
        
        if include_args:
            metadata['args_count'] = len(args)
            metadata['kwargs_keys'] = list(kwargs.keys())
            
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=op_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=True,
                metadata=metadata
            )
            
            self._record_performance_metrics(metrics)
            return result
            
        except Exception as e:
            end_time = time.time()
            
            if track_errors:
                metrics = PerformanceMetrics(
                    operation_name=op_name,
                    duration_seconds=end_time - start_time,
                    start_time=start_time,
                    end_time=end_time,
                    success=False,
                    error_message=str(e),
                    metadata=metadata
                )
                self._record_performance_metrics(metrics)
                
            raise
            
    async def _track_async_operation(self, func: Callable, op_name: str,
                                    args: tuple, kwargs: dict,
                                    include_args: bool, track_errors: bool) -> Any:
        """Rastreia operação assíncrona."""
        start_time = time.time()
        metadata = {}
        
        if include_args:
            metadata['args_count'] = len(args)
            metadata['kwargs_keys'] = list(kwargs.keys())
            
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=op_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=True,
                metadata=metadata
            )
            
            self._record_performance_metrics(metrics)
            return result
            
        except Exception as e:
            end_time = time.time()
            
            if track_errors:
                metrics = PerformanceMetrics(
                    operation_name=op_name,
                    duration_seconds=end_time - start_time,
                    start_time=start_time,
                    end_time=end_time,
                    success=False,
                    error_message=str(e),
                    metadata=metadata
                )
                self._record_performance_metrics(metrics)
                
            raise
            
    @contextmanager
    def measure_time(self, operation_name: str, metadata: Dict[str, Any] = None):
        """Context manager para medição manual de tempo.
        
        Args:
            operation_name: Nome da operação
            metadata: Metadados opcionais
            
        Example:
            with tracker.measure_time('database_query'):
                result = db.query('SELECT * FROM users')
        """
        start_time = time.time()
        
        try:
            yield
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=True,
                metadata=metadata or {}
            )
            
            self._record_performance_metrics(metrics)
            
        except Exception as e:
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=False,
                error_message=str(e),
                metadata=metadata or {}
            )
            
            self._record_performance_metrics(metrics)
            raise
            
    @asynccontextmanager
    async def measure_time_async(self, operation_name: str, metadata: Dict[str, Any] = None):
        """Context manager assíncrono para medição de tempo.
        
        Args:
            operation_name: Nome da operação
            metadata: Metadados opcionais
            
        Example:
            async with tracker.measure_time_async('async_operation'):
                result = await some_async_function()
        """
        start_time = time.time()
        
        try:
            yield
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=True,
                metadata=metadata or {}
            )
            
            self._record_performance_metrics(metrics)
            
        except Exception as e:
            end_time = time.time()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                duration_seconds=end_time - start_time,
                start_time=start_time,
                end_time=end_time,
                success=False,
                error_message=str(e),
                metadata=metadata or {}
            )
            
            self._record_performance_metrics(metrics)
            raise
            
    def _record_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        """Registra métricas de performance no coletor."""
        # Armazenar no histórico local
        self._operation_history[metrics.operation_name].append(metrics)
        
        # Registrar no coletor de métricas
        labels = {
            'operation': metrics.operation_name,
            'success': str(metrics.success).lower()
        }
        
        # Contador de operações
        self.metrics_collector.increment_counter(
            'operations_total', 
            labels=labels
        )
        
        # Histograma de duração
        self.metrics_collector.record_histogram(
            'operation_duration_seconds',
            metrics.duration_seconds,
            labels={'operation': metrics.operation_name}
        )
        
        # Gauge da última duração
        self.metrics_collector.record_gauge(
            'operation_last_duration_seconds',
            metrics.duration_seconds,
            labels={'operation': metrics.operation_name}
        )
        
        # Contador de erros se aplicável
        if not metrics.success:
            self.metrics_collector.increment_counter(
                'operation_errors_total',
                labels={'operation': metrics.operation_name}
            )
            
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Obtém estatísticas de uma operação.
        
        Args:
            operation_name: Nome da operação
            
        Returns:
            Dicionário com estatísticas da operação
        """
        history = self._operation_history.get(operation_name, deque())
        
        if not history:
            return {'operation': operation_name, 'count': 0}
            
        durations = [m.duration_seconds for m in history]
        successes = [m.success for m in history]
        
        return {
            'operation': operation_name,
            'count': len(history),
            'success_rate': sum(successes) / len(successes),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'total_duration': sum(durations),
            'last_execution': history[-1].end_time if history else None
        }
        
    def get_all_operations_stats(self) -> Dict[str, Dict[str, Any]]:
        """Obtém estatísticas de todas as operações."""
        return {
            op_name: self.get_operation_stats(op_name)
            for op_name in self._operation_history.keys()
        }
        
    def get_throughput_stats(self, operation_name: str, window_minutes: int = 5) -> Dict[str, float]:
        """Calcula estatísticas de throughput para uma operação.
        
        Args:
            operation_name: Nome da operação
            window_minutes: Janela de tempo em minutos
            
        Returns:
            Estatísticas de throughput
        """
        history = self._operation_history.get(operation_name, deque())
        
        if not history:
            return {'operations_per_second': 0.0, 'operations_per_minute': 0.0}
            
        cutoff_time = time.time() - (window_minutes * 60)
        recent_operations = [m for m in history if m.end_time >= cutoff_time]
        
        if not recent_operations:
            return {'operations_per_second': 0.0, 'operations_per_minute': 0.0}
            
        time_span = recent_operations[-1].end_time - recent_operations[0].start_time
        
        if time_span <= 0:
            return {'operations_per_second': 0.0, 'operations_per_minute': 0.0}
            
        ops_per_second = len(recent_operations) / time_span
        
        return {
            'operations_per_second': ops_per_second,
            'operations_per_minute': ops_per_second * 60,
            'window_minutes': window_minutes,
            'operations_in_window': len(recent_operations)
        }
        
    def clear_history(self, operation_name: Optional[str] = None) -> None:
        """Limpa histórico de operações.
        
        Args:
            operation_name: Nome da operação específica (None para todas)
        """
        if operation_name:
            self._operation_history[operation_name].clear()
        else:
            self._operation_history.clear()


# Instância global para facilitar uso
performance_tracker = PerformanceTracker()

# Decorators de conveniência
track_performance = performance_tracker.track_performance
measure_time = performance_tracker.measure_time
measure_time_async = performance_tracker.measure_time_async