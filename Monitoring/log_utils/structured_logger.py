"""Structured Logger Module

Implementa logging estruturado em formato JSON com:
- Contexto automático (timestamp, thread, processo)
- Integração com métricas
- Níveis de log configuráveis
- Correlação de requests
- Sampling de logs
"""

import json
import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum
import os
import sys


class LogLevel(Enum):
    """Níveis de log"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Contexto de log"""
    correlation_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StructuredLogger:
    """Logger estruturado com formato JSON"""
    
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
        self._logger = logging.getLogger('PySocketCommLib')
        self._context_stack = threading.local()
        self._sampling_rate = 1.0  # 100% por padrão
        self._metrics_integration = None
        
        # Configuração padrão
        self._setup_default_logger()
    
    def _setup_default_logger(self):
        """Configura o logger padrão"""
        self._logger.setLevel(logging.INFO)
        
        # Remove handlers existentes
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        
        # Handler para console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter JSON personalizado
        from .formatter import LogFormatter
        formatter = LogFormatter()
        console_handler.setFormatter(formatter)
        
        self._logger.addHandler(console_handler)
        self._logger.propagate = False
    
    def configure(self, level: Union[str, LogLevel] = LogLevel.INFO,
                 handlers: Optional[List[logging.Handler]] = None,
                 sampling_rate: float = 1.0) -> None:
        """Configura o logger
        
        Args:
            level: Nível de log
            handlers: Lista de handlers personalizados
            sampling_rate: Taxa de amostragem (0.0 a 1.0)
        """
        if isinstance(level, LogLevel):
            level = level.value
        
        self._logger.setLevel(getattr(logging, level.upper()))
        self._sampling_rate = max(0.0, min(1.0, sampling_rate))
        
        if handlers:
            # Remove handlers existentes
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)
            
            # Adiciona novos handlers
            for handler in handlers:
                self._logger.addHandler(handler)
    
    def set_metrics_integration(self, metrics_collector):
        """Define integração com coletor de métricas"""
        self._metrics_integration = metrics_collector
    
    def _should_sample(self) -> bool:
        """Determina se deve fazer sampling do log"""
        if self._sampling_rate >= 1.0:
            return True
        if self._sampling_rate <= 0.0:
            return False
        
        import random
        return random.random() < self._sampling_rate
    
    def _get_context_stack(self) -> List[LogContext]:
        """Obtém a pilha de contexto da thread atual"""
        if not hasattr(self._context_stack, 'stack'):
            self._context_stack.stack = []
        return self._context_stack.stack
    
    def _get_current_context(self) -> Optional[LogContext]:
        """Obtém o contexto atual"""
        stack = self._get_context_stack()
        return stack[-1] if stack else None
    
    def _build_log_entry(self, level: LogLevel, message: str, 
                        extra: Optional[Dict[str, Any]] = None,
                        exception: Optional[Exception] = None) -> Dict[str, Any]:
        """Constrói entrada de log estruturada"""
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        entry = {
            'timestamp': timestamp,
            'level': level.value,
            'message': message,
            'logger': 'PySocketCommLib',
            'thread_id': threading.get_ident(),
            'process_id': os.getpid()
        }
        
        # Adiciona contexto atual
        current_context = self._get_current_context()
        if current_context:
            entry['context'] = asdict(current_context)
        
        # Adiciona informações extras
        if extra:
            entry['extra'] = extra
        
        # Adiciona informações de exceção
        if exception:
            entry['exception'] = {
                'type': type(exception).__name__,
                'message': str(exception),
                'module': getattr(exception, '__module__', None)
            }
            
            # Adiciona stack trace se disponível
            import traceback
            entry['exception']['traceback'] = traceback.format_exc()
        
        return entry
    
    def _log(self, level: LogLevel, message: str, 
            extra: Optional[Dict[str, Any]] = None,
            exception: Optional[Exception] = None) -> None:
        """Método interno de log"""
        if not self._should_sample():
            return
        
        # Integração com métricas
        if self._metrics_integration:
            self._metrics_integration.increment_counter(f'logs.{level.value.lower()}')
            if exception:
                self._metrics_integration.increment_counter('logs.exceptions')
        
        # Constrói entrada de log
        log_entry = self._build_log_entry(level, message, extra, exception)
        
        # Envia para o logger
        log_level = getattr(logging, level.value)
        self._logger.log(log_level, json.dumps(log_entry, ensure_ascii=False))
    
    # Métodos de log públicos
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log de debug"""
        self._log(LogLevel.DEBUG, message, extra)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log de informação"""
        self._log(LogLevel.INFO, message, extra)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log de aviso"""
        self._log(LogLevel.WARNING, message, extra)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None,
             exception: Optional[Exception] = None) -> None:
        """Log de erro"""
        self._log(LogLevel.ERROR, message, extra, exception)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None,
                exception: Optional[Exception] = None) -> None:
        """Log crítico"""
        self._log(LogLevel.CRITICAL, message, extra, exception)
    
    def exception(self, message: str, exception: Exception,
                 extra: Optional[Dict[str, Any]] = None) -> None:
        """Log de exceção"""
        self._log(LogLevel.ERROR, message, extra, exception)
    
    # Gerenciamento de contexto
    @contextmanager
    def context(self, correlation_id: Optional[str] = None, **kwargs):
        """Context manager para adicionar contexto aos logs
        
        Args:
            correlation_id: ID de correlação (gerado automaticamente se não fornecido)
            **kwargs: Outros campos do contexto
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        context = LogContext(
            correlation_id=correlation_id,
            user_id=kwargs.get('user_id'),
            session_id=kwargs.get('session_id'),
            request_id=kwargs.get('request_id'),
            component=kwargs.get('component'),
            operation=kwargs.get('operation'),
            metadata=kwargs.get('metadata')
        )
        
        stack = self._get_context_stack()
        stack.append(context)
        
        try:
            yield context
        finally:
            stack.pop()
    
    def push_context(self, correlation_id: Optional[str] = None, **kwargs) -> LogContext:
        """Adiciona contexto à pilha"""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        context = LogContext(
            correlation_id=correlation_id,
            user_id=kwargs.get('user_id'),
            session_id=kwargs.get('session_id'),
            request_id=kwargs.get('request_id'),
            component=kwargs.get('component'),
            operation=kwargs.get('operation'),
            metadata=kwargs.get('metadata')
        )
        
        stack = self._get_context_stack()
        stack.append(context)
        
        return context
    
    def pop_context(self) -> Optional[LogContext]:
        """Remove contexto da pilha"""
        stack = self._get_context_stack()
        return stack.pop() if stack else None
    
    def clear_context(self) -> None:
        """Limpa toda a pilha de contexto"""
        stack = self._get_context_stack()
        stack.clear()
    
    # Métodos de conveniência
    def log_request_start(self, method: str, path: str, 
                         request_id: Optional[str] = None,
                         user_id: Optional[str] = None) -> LogContext:
        """Log de início de request"""
        context = self.push_context(
            request_id=request_id or str(uuid.uuid4()),
            user_id=user_id,
            component='http_server',
            operation='request_handling'
        )
        
        self.info(f"Request started: {method} {path}", {
            'http_method': method,
            'http_path': path,
            'request_start': True
        })
        
        return context
    
    def log_request_end(self, status_code: int, duration_ms: float,
                       response_size: Optional[int] = None) -> None:
        """Log de fim de request"""
        extra = {
            'http_status_code': status_code,
            'duration_ms': duration_ms,
            'request_end': True
        }
        
        if response_size is not None:
            extra['response_size_bytes'] = response_size
        
        level = LogLevel.INFO if status_code < 400 else LogLevel.WARNING
        if status_code >= 500:
            level = LogLevel.ERROR
        
        self._log(level, f"Request completed with status {status_code}", extra)
        self.pop_context()
    
    def log_database_query(self, query: str, duration_ms: float,
                          rows_affected: Optional[int] = None) -> None:
        """Log de query de banco de dados"""
        extra = {
            'database_query': query[:200] + '...' if len(query) > 200 else query,
            'query_duration_ms': duration_ms,
            'database_operation': True
        }
        
        if rows_affected is not None:
            extra['rows_affected'] = rows_affected
        
        self.info("Database query executed", extra)
    
    def log_cache_operation(self, operation: str, key: str, hit: bool,
                           duration_ms: Optional[float] = None) -> None:
        """Log de operação de cache"""
        extra = {
            'cache_operation': operation,
            'cache_key': key,
            'cache_hit': hit,
            'cache_operation_log': True
        }
        
        if duration_ms is not None:
            extra['operation_duration_ms'] = duration_ms
        
        self.debug(f"Cache {operation}: {'HIT' if hit else 'MISS'} for key {key}", extra)
    
    def log_performance_metric(self, metric_name: str, value: float,
                              unit: str = 'ms', tags: Optional[Dict[str, str]] = None) -> None:
        """Log de métrica de performance"""
        extra = {
            'metric_name': metric_name,
            'metric_value': value,
            'metric_unit': unit,
            'performance_metric': True
        }
        
        if tags:
            extra['metric_tags'] = tags
        
        self.info(f"Performance metric: {metric_name} = {value}{unit}", extra)


# Instância global
logger = StructuredLogger()