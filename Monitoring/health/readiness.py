"""Readiness Checker Module

Implementa verificações de prontidão do sistema para determinar se:
- Dependências externas estão disponíveis
- Serviços críticos estão funcionando
- Sistema está pronto para receber tráfego
- Configurações necessárias estão presentes
"""

import asyncio
import socket
import time
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import urllib.request
import urllib.error


class ReadinessStatus(Enum):
    """Status de prontidão dos componentes"""
    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


@dataclass
class ReadinessCheckResult:
    """Resultado de uma verificação de prontidão"""
    name: str
    status: ReadinessStatus
    message: str
    duration_ms: float
    timestamp: float
    details: Optional[Dict[str, Any]] = None


class ReadinessChecker:
    """Verificador de prontidão do sistema"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, ReadinessCheckResult] = {}
        self._lock = threading.RLock()
        self._dependencies: Dict[str, Dict[str, Any]] = {}
        self._timeout = 5  # segundos
        
        # Registrar verificações padrão
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Registra verificações de prontidão padrão"""
        self.register_check("basic_connectivity", self._check_basic_connectivity)
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Registra uma nova verificação de prontidão
        
        Args:
            name: Nome da verificação
            check_func: Função que retorna ReadinessCheckResult
        """
        with self._lock:
            self._checks[name] = check_func
    
    def unregister_check(self, name: str) -> None:
        """Remove uma verificação de prontidão"""
        with self._lock:
            self._checks.pop(name, None)
            self._results.pop(name, None)
    
    def add_database_dependency(self, name: str, host: str, port: int, 
                               database: str = None, timeout: int = 5) -> None:
        """Adiciona uma dependência de banco de dados
        
        Args:
            name: Nome da dependência
            host: Host do banco
            port: Porta do banco
            database: Nome do banco (opcional)
            timeout: Timeout da conexão
        """
        self._dependencies[f"db_{name}"] = {
            "type": "database",
            "host": host,
            "port": port,
            "database": database,
            "timeout": timeout
        }
        
        # Registra a verificação automaticamente
        self.register_check(f"db_{name}", 
                          lambda: self._check_database_dependency(f"db_{name}"))
    
    def add_http_dependency(self, name: str, url: str, 
                           expected_status: int = 200, timeout: int = 5) -> None:
        """Adiciona uma dependência HTTP
        
        Args:
            name: Nome da dependência
            url: URL para verificar
            expected_status: Status HTTP esperado
            timeout: Timeout da requisição
        """
        self._dependencies[f"http_{name}"] = {
            "type": "http",
            "url": url,
            "expected_status": expected_status,
            "timeout": timeout
        }
        
        # Registra a verificação automaticamente
        self.register_check(f"http_{name}", 
                          lambda: self._check_http_dependency(f"http_{name}"))
    
    def add_tcp_dependency(self, name: str, host: str, port: int, timeout: int = 5) -> None:
        """Adiciona uma dependência TCP
        
        Args:
            name: Nome da dependência
            host: Host para conectar
            port: Porta para conectar
            timeout: Timeout da conexão
        """
        self._dependencies[f"tcp_{name}"] = {
            "type": "tcp",
            "host": host,
            "port": port,
            "timeout": timeout
        }
        
        # Registra a verificação automaticamente
        self.register_check(f"tcp_{name}", 
                          lambda: self._check_tcp_dependency(f"tcp_{name}"))
    
    def run_check(self, name: str) -> Optional[ReadinessCheckResult]:
        """Executa uma verificação específica"""
        if name not in self._checks:
            return None
        
        start_time = time.time()
        try:
            result = self._checks[name]()
            if not isinstance(result, ReadinessCheckResult):
                result = ReadinessCheckResult(
                    name=name,
                    status=ReadinessStatus.UNKNOWN,
                    message="Invalid check result format",
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=time.time()
                )
        except Exception as e:
            result = ReadinessCheckResult(
                name=name,
                status=ReadinessStatus.NOT_READY,
                message=f"Check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
        
        with self._lock:
            self._results[name] = result
        
        return result
    
    def run_all_checks(self) -> Dict[str, ReadinessCheckResult]:
        """Executa todas as verificações registradas"""
        results = {}
        for name in list(self._checks.keys()):
            result = self.run_check(name)
            if result:
                results[name] = result
        return results
    
    async def run_all_checks_async(self) -> Dict[str, ReadinessCheckResult]:
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
                results[name] = ReadinessCheckResult(
                    name=name,
                    status=ReadinessStatus.NOT_READY,
                    message=f"Async check failed: {str(e)}",
                    duration_ms=0,
                    timestamp=time.time()
                )
        
        return results
    
    def is_ready(self) -> bool:
        """Verifica se o sistema está pronto"""
        if not self._results:
            # Se não há resultados, executa todas as verificações
            self.run_all_checks()
        
        return all(result.status == ReadinessStatus.READY 
                  for result in self._results.values())
    
    def get_readiness_summary(self) -> Dict[str, Any]:
        """Retorna um resumo do status de prontidão"""
        is_ready = self.is_ready()
        
        return {
            "ready": is_ready,
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
                "ready_checks": sum(1 for r in self._results.values() 
                                   if r.status == ReadinessStatus.READY),
                "not_ready_checks": sum(1 for r in self._results.values() 
                                       if r.status == ReadinessStatus.NOT_READY),
                "unknown_checks": sum(1 for r in self._results.values() 
                                     if r.status == ReadinessStatus.UNKNOWN)
            }
        }
    
    # Verificações de dependências
    def _check_database_dependency(self, dep_name: str) -> ReadinessCheckResult:
        """Verifica conectividade com banco de dados"""
        if dep_name not in self._dependencies:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.UNKNOWN,
                message="Dependency not found",
                duration_ms=0,
                timestamp=time.time()
            )
        
        dep = self._dependencies[dep_name]
        start_time = time.time()
        
        try:
            # Tenta conectar via TCP primeiro
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(dep["timeout"])
            result = sock.connect_ex((dep["host"], dep["port"]))
            sock.close()
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result == 0:
                return ReadinessCheckResult(
                    name=dep_name,
                    status=ReadinessStatus.READY,
                    message=f"Database {dep['host']}:{dep['port']} is reachable",
                    duration_ms=duration_ms,
                    timestamp=time.time(),
                    details={
                        "host": dep["host"],
                        "port": dep["port"],
                        "database": dep.get("database"),
                        "connection_time_ms": duration_ms
                    }
                )
            else:
                return ReadinessCheckResult(
                    name=dep_name,
                    status=ReadinessStatus.NOT_READY,
                    message=f"Cannot connect to database {dep['host']}:{dep['port']}",
                    duration_ms=duration_ms,
                    timestamp=time.time()
                )
        
        except Exception as e:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.NOT_READY,
                message=f"Database check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
    
    def _check_http_dependency(self, dep_name: str) -> ReadinessCheckResult:
        """Verifica dependência HTTP"""
        if dep_name not in self._dependencies:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.UNKNOWN,
                message="Dependency not found",
                duration_ms=0,
                timestamp=time.time()
            )
        
        dep = self._dependencies[dep_name]
        start_time = time.time()
        
        try:
            req = urllib.request.Request(dep["url"])
            req.add_header('User-Agent', 'PySocketCommLib-HealthCheck/1.0')
            
            with urllib.request.urlopen(req, timeout=dep["timeout"]) as response:
                status_code = response.getcode()
                duration_ms = (time.time() - start_time) * 1000
                
                if status_code == dep["expected_status"]:
                    return ReadinessCheckResult(
                        name=dep_name,
                        status=ReadinessStatus.READY,
                        message=f"HTTP endpoint {dep['url']} returned {status_code}",
                        duration_ms=duration_ms,
                        timestamp=time.time(),
                        details={
                            "url": dep["url"],
                            "status_code": status_code,
                            "expected_status": dep["expected_status"],
                            "response_time_ms": duration_ms
                        }
                    )
                else:
                    return ReadinessCheckResult(
                        name=dep_name,
                        status=ReadinessStatus.NOT_READY,
                        message=f"HTTP endpoint {dep['url']} returned {status_code}, expected {dep['expected_status']}",
                        duration_ms=duration_ms,
                        timestamp=time.time()
                    )
        
        except urllib.error.HTTPError as e:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.NOT_READY,
                message=f"HTTP error {e.code}: {e.reason}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
        except Exception as e:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.NOT_READY,
                message=f"HTTP check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
    
    def _check_tcp_dependency(self, dep_name: str) -> ReadinessCheckResult:
        """Verifica dependência TCP"""
        if dep_name not in self._dependencies:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.UNKNOWN,
                message="Dependency not found",
                duration_ms=0,
                timestamp=time.time()
            )
        
        dep = self._dependencies[dep_name]
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(dep["timeout"])
            result = sock.connect_ex((dep["host"], dep["port"]))
            sock.close()
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result == 0:
                return ReadinessCheckResult(
                    name=dep_name,
                    status=ReadinessStatus.READY,
                    message=f"TCP service {dep['host']}:{dep['port']} is reachable",
                    duration_ms=duration_ms,
                    timestamp=time.time(),
                    details={
                        "host": dep["host"],
                        "port": dep["port"],
                        "connection_time_ms": duration_ms
                    }
                )
            else:
                return ReadinessCheckResult(
                    name=dep_name,
                    status=ReadinessStatus.NOT_READY,
                    message=f"Cannot connect to TCP service {dep['host']}:{dep['port']}",
                    duration_ms=duration_ms,
                    timestamp=time.time()
                )
        
        except Exception as e:
            return ReadinessCheckResult(
                name=dep_name,
                status=ReadinessStatus.NOT_READY,
                message=f"TCP check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=time.time()
            )
    
    def _check_basic_connectivity(self) -> ReadinessCheckResult:
        """Verificação básica de conectividade"""
        try:
            # Tenta resolver DNS do Google
            socket.gethostbyname('google.com')
            
            return ReadinessCheckResult(
                name="basic_connectivity",
                status=ReadinessStatus.READY,
                message="Basic network connectivity is working",
                duration_ms=0,
                timestamp=time.time(),
                details={"dns_resolution": "working"}
            )
        except Exception as e:
            return ReadinessCheckResult(
                name="basic_connectivity",
                status=ReadinessStatus.NOT_READY,
                message=f"Basic connectivity check failed: {str(e)}",
                duration_ms=0,
                timestamp=time.time()
            )