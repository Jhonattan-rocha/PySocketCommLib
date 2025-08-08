"""Health Checker Module

Implementa verificações de saúde do sistema para monitorar:
- Conectividade de banco de dados
- Uso de recursos do sistema
- Status de serviços externos
- Integridade de componentes críticos
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """Status de saúde dos componentes"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Resultado de uma verificação de saúde"""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: float
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """Verificador de saúde do sistema"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self._lock = threading.RLock()
        self._running = False
        self._check_interval = 30  # segundos
        self._background_thread: Optional[threading.Thread] = None
        
        # Registrar verificações padrão
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Registra verificações de saúde padrão"""
        self.register_check("system_resources", self._check_system_resources)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory_usage", self._check_memory_usage)
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Registra uma nova verificação de saúde
        
        Args:
            name: Nome da verificação
            check_func: Função que retorna HealthCheckResult
        """
        with self._lock:
            self._checks[name] = check_func
    
    def unregister_check(self, name: str) -> None:
        """Remove uma verificação de saúde"""
        with self._lock:
            self._checks.pop(name, None)
            self._results.pop(name, None)
    
    def run_check(self, name: str) -> Optional[HealthCheckResult]:
        """Executa uma verificação específica"""
        if name not in self._checks:
            return None
        
        start_time = time.time()
        try:
            result = self._checks[name]()
            if not isinstance(result, HealthCheckResult):
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message="Invalid check result format",
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=time.time()
                )
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
        
        with self._lock:
            self._results[name] = result
        
        return result
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Executa todas as verificações registradas"""
        results = {}
        for name in list(self._checks.keys()):
            result = self.run_check(name)
            if result:
                results[name] = result
        return results
    
    async def run_all_checks_async(self) -> Dict[str, HealthCheckResult]:
        """Executa todas as verificações de forma assíncrona"""
        loop = asyncio.get_event_loop()
        tasks = []
        
        for name in list(self._checks.keys()):
            task = loop.run_in_executor(None, self.run_check, name)
            tasks.append((name, task))
        
        results = {}
        for name, task in tasks:
            try:
                result = await task
                if result:
                    results[name] = result
            except Exception as e:
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Async check failed: {str(e)}",
                    duration_ms=0,
                    timestamp=time.time()
                )
        
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Retorna o status geral de saúde"""
        if not self._results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in self._results.values()]
        
        if any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Retorna um resumo do status de saúde"""
        overall_status = self.get_overall_status()
        
        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp,
                    "details": result.details
                }
                for name, result in self._results.items()
            },
            "summary": {
                "total_checks": len(self._results),
                "healthy": sum(1 for r in self._results.values() if r.status == HealthStatus.HEALTHY),
                "degraded": sum(1 for r in self._results.values() if r.status == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for r in self._results.values() if r.status == HealthStatus.UNHEALTHY),
                "unknown": sum(1 for r in self._results.values() if r.status == HealthStatus.UNKNOWN)
            }
        }
    
    def start_background_checks(self, interval: int = 30) -> None:
        """Inicia verificações em background"""
        if self._running:
            return
        
        self._check_interval = interval
        self._running = True
        self._background_thread = threading.Thread(target=self._background_check_loop, daemon=True)
        self._background_thread.start()
    
    def stop_background_checks(self) -> None:
        """Para as verificações em background"""
        self._running = False
        if self._background_thread:
            self._background_thread.join(timeout=5)
    
    def _background_check_loop(self) -> None:
        """Loop de verificações em background"""
        while self._running:
            try:
                self.run_all_checks()
            except Exception as e:
                print(f"Background health check error: {e}")
            
            # Aguarda o intervalo ou até ser interrompido
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    # Verificações padrão
    def _check_system_resources(self) -> HealthCheckResult:
        """Verifica recursos do sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3)
            }
            
            if cpu_percent > 90 or memory.percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"High resource usage: CPU {cpu_percent}%, Memory {memory.percent}%"
            elif cpu_percent > 70 or memory.percent > 70:
                status = HealthStatus.DEGRADED
                message = f"Moderate resource usage: CPU {cpu_percent}%, Memory {memory.percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Normal resource usage: CPU {cpu_percent}%, Memory {memory.percent}%"
            
            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                duration_ms=0,
                timestamp=time.time(),
                details=details
            )
        except Exception as e:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check system resources: {str(e)}",
                duration_ms=0,
                timestamp=time.time()
            )
    
    def _check_disk_space(self) -> HealthCheckResult:
        """Verifica espaço em disco"""
        try:
            disk = psutil.disk_usage('/')
            free_percent = (disk.free / disk.total) * 100
            
            details = {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_percent": free_percent
            }
            
            if free_percent < 5:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk space: {free_percent:.1f}% free"
            elif free_percent < 15:
                status = HealthStatus.DEGRADED
                message = f"Low disk space: {free_percent:.1f}% free"
            else:
                status = HealthStatus.HEALTHY
                message = f"Sufficient disk space: {free_percent:.1f}% free"
            
            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                duration_ms=0,
                timestamp=time.time(),
                details=details
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check disk space: {str(e)}",
                duration_ms=0,
                timestamp=time.time()
            )
    
    def _check_memory_usage(self) -> HealthCheckResult:
        """Verifica uso detalhado de memória"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            details = {
                "virtual_memory": {
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "percent": memory.percent,
                    "used_gb": memory.used / (1024**3)
                },
                "swap_memory": {
                    "total_gb": swap.total / (1024**3),
                    "used_gb": swap.used / (1024**3),
                    "percent": swap.percent
                }
            }
            
            if memory.percent > 95 or swap.percent > 80:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: RAM {memory.percent}%, Swap {swap.percent}%"
            elif memory.percent > 85 or swap.percent > 50:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: RAM {memory.percent}%, Swap {swap.percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Normal memory usage: RAM {memory.percent}%, Swap {swap.percent}%"
            
            return HealthCheckResult(
                name="memory_usage",
                status=status,
                message=message,
                duration_ms=0,
                timestamp=time.time(),
                details=details
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check memory usage: {str(e)}",
                duration_ms=0,
                timestamp=time.time()
            )