# Sistema de Monitoramento PySocketCommLib

Sistema completo de monitoramento, métricas e observabilidade para aplicações PySocketCommLib.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Componentes](#componentes)
- [Instalação](#instalação)
- [Uso Rápido](#uso-rápido)
- [Configuração Detalhada](#configuração-detalhada)
- [Endpoints HTTP](#endpoints-http)
- [Integração com Prometheus](#integração-com-prometheus)
- [Exemplos Avançados](#exemplos-avançados)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

O sistema de monitoramento oferece:

- **Coleta de Métricas**: Contadores, gauges, histogramas e métricas do sistema
- **Tracking de Performance**: Decorators e context managers para medir performance
- **Health Checks**: Verificações de saúde do sistema e dependências
- **Readiness Checks**: Verificações de prontidão para receber tráfego
- **Logging Estruturado**: Logs em formato JSON com contexto automático
- **Endpoints HTTP**: API REST para exposição de métricas e status
- **Compatibilidade Prometheus**: Exportação de métricas no formato Prometheus

## 🧩 Componentes

### MetricsCollector
Coleta e armazena métricas da aplicação:
- Contadores (incrementais)
- Gauges (valores instantâneos)
- Histogramas (distribuições)
- Métricas do sistema (CPU, memória, disco)

### PerformanceTracker
Rastreia performance de operações:
- Decorators para funções
- Context managers para blocos de código
- Suporte assíncrono
- Tracking automático de erros

### HealthChecker
Verifica saúde do sistema:
- Verificações padrão (recursos, disco, memória)
- Verificações customizadas
- Execução em background
- Status agregado

### ReadinessChecker
Verifica prontidão para receber tráfego:
- Dependências TCP
- Dependências HTTP
- Verificações de banco de dados
- Status de prontidão

### StructuredLogger
Logging estruturado em JSON:
- Contexto automático
- Correlação de requests
- Integração com métricas
- Sampling de logs

### HealthEndpoints
API HTTP para monitoramento:
- Endpoints de saúde
- Endpoints de métricas
- Handlers customizados
- Suporte CORS

## 🚀 Instalação

```bash
# Dependências necessárias
pip install psutil requests

# Para desenvolvimento/testes
pip install pytest pytest-asyncio
```

## ⚡ Uso Rápido

```python
from Monitoring import (
    MetricsCollector,
    PerformanceTracker,
    HealthChecker,
    StructuredLogger,
    HealthEndpoints
)

# Inicialização básica
metrics = MetricsCollector()
tracker = PerformanceTracker()
health = HealthChecker()
logger = StructuredLogger()
endpoints = HealthEndpoints()

# Coleta de métricas
metrics.increment_counter('requests.total')
metrics.record_gauge('memory.usage', 1024)

# Tracking de performance
@tracker.track_performance
def my_function():
    # Sua lógica aqui
    pass

# Logging estruturado
logger.info("Operação realizada", {"user_id": "123"})

# Inicia endpoints HTTP
endpoints.start()
print(f"Monitoramento disponível em: {endpoints.get_url()}")
```

## ⚙️ Configuração Detalhada

### MetricsCollector

```python
from Monitoring.metrics import MetricsCollector

# Singleton - sempre retorna a mesma instância
metrics = MetricsCollector()

# Contadores
metrics.increment_counter('http.requests.total')
metrics.increment_counter('http.requests.total', 5)  # Incrementa por 5

# Gauges
metrics.record_gauge('memory.usage.bytes', 1073741824)
metrics.record_gauge('active.connections', 42)

# Histogramas
metrics.record_histogram('request.duration.ms', 150.5)
metrics.record_histogram('response.size.bytes', 2048)

# Métricas do sistema (automáticas)
metrics.collect_system_metrics()

# Resumo das métricas
summary = metrics.get_metrics_summary()
print(summary)

# Exportação Prometheus
prometheus_format = metrics.export_prometheus()
print(prometheus_format)
```

### PerformanceTracker

```python
from Monitoring.metrics import PerformanceTracker
import asyncio

tracker = PerformanceTracker()

# Decorator para funções síncronas
@tracker.track_performance
def process_data(data):
    # Processamento dos dados
    return processed_data

# Decorator para funções assíncronas
@tracker.track_async_performance
async def async_process_data(data):
    # Processamento assíncrono
    return processed_data

# Context manager
with tracker.track_performance('database.query'):
    # Operação de banco de dados
    result = db.query("SELECT * FROM users")

# Context manager assíncrono
async def async_operation():
    async with tracker.track_async_performance('api.call'):
        # Chamada de API assíncrona
        response = await api_client.get('/data')
```

### HealthChecker

```python
from Monitoring.health import HealthChecker, HealthStatus, HealthCheckResult
import time

health = HealthChecker()

# Verificação customizada
def database_check():
    try:
        # Tenta conectar ao banco
        db.ping()
        return HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
            duration_ms=10,
            timestamp=time.time()
        )
    except Exception as e:
        return HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database error: {str(e)}",
            duration_ms=5000,  # Timeout
            timestamp=time.time()
        )

# Registra verificação
health.register_check("database", database_check)

# Executa verificação específica
result = health.run_check("database")
print(f"Database status: {result.status}")

# Executa todas as verificações
all_results = health.run_all_checks()

# Status geral
overall_status = health.get_overall_status()
print(f"Overall health: {overall_status}")

# Verificações em background
health.start_background_checks(interval=30)  # A cada 30 segundos
# ... aplicação rodando ...
health.stop_background_checks()
```

### ReadinessChecker

```python
from Monitoring.health import ReadinessChecker

readiness = ReadinessChecker()

# Dependência de banco de dados
readiness.add_database_dependency(
    name="main_db",
    connection_string="postgresql://user:pass@localhost:5432/db",
    timeout=5
)

# Dependência HTTP
readiness.add_http_dependency(
    name="api_service",
    url="https://api.example.com/health",
    expected_status=200,
    timeout=10
)

# Dependência TCP
readiness.add_tcp_dependency(
    name="redis",
    host="localhost",
    port=6379,
    timeout=3
)

# Verifica prontidão
if readiness.is_ready():
    print("Sistema pronto para receber tráfego")
else:
    print("Sistema não está pronto")
    # Detalhes das verificações
    results = readiness.run_all_checks()
    for name, result in results.items():
        print(f"{name}: {result.status} - {result.message}")
```

### StructuredLogger

```python
from Monitoring.logging import StructuredLogger, LogLevel

logger = StructuredLogger()

# Configuração de nível
logger.set_level(LogLevel.INFO)

# Logging básico
logger.info("Usuário logado", {"user_id": "123", "ip": "192.168.1.1"})
logger.warning("Tentativa de acesso negada", {"user_id": "456", "reason": "invalid_token"})
logger.error("Erro de conexão", {"service": "database", "error_code": "CONN_TIMEOUT"})

# Contexto de request
with logger.context(request_id="req-123", user_id="user-456"):
    logger.info("Processando request")
    # ... processamento ...
    logger.info("Request processado com sucesso")

# Logging de exceções
try:
    risky_operation()
except Exception as e:
    logger.exception("Erro na operação", e, {"operation": "risky_operation"})

# Logging de requests HTTP
request_context = logger.log_request_start("GET", "/api/users", user_id="123")
# ... processamento do request ...
logger.log_request_end(200, 150.5, 1024)  # status, duration_ms, response_size

# Logging de operações de banco
logger.log_database_query("SELECT * FROM users WHERE id = ?", 45.2, 10)

# Logging de cache
logger.log_cache_operation("get", "user:123", hit=True, 2.1)

# Sampling (para reduzir volume de logs)
logger.set_sampling_rate(0.1)  # 10% dos logs
```

## 🌐 Endpoints HTTP

O `HealthEndpoints` expõe uma API REST para monitoramento:

```python
from Monitoring.endpoints import HealthEndpoints

endpoints = HealthEndpoints(host='0.0.0.0', port=8080)
endpoints.start()

print(f"Monitoramento disponível em: {endpoints.get_url()}")
```

### Endpoints Disponíveis

| Endpoint | Método | Descrição |
|----------|--------|----------|
| `/health` | GET | Status geral de saúde |
| `/health/live` | GET | Liveness check (aplicação rodando) |
| `/health/ready` | GET | Readiness check (pronto para tráfego) |
| `/metrics` | GET | Métricas em formato JSON |
| `/metrics?format=prometheus` | GET | Métricas em formato Prometheus |
| `/status` | GET | Status detalhado do sistema |

### Exemplos de Resposta

**GET /health**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "checks": {
    "system_resources": {
      "status": "healthy",
      "message": "System resources OK",
      "duration_ms": 5
    },
    "database": {
      "status": "healthy",
      "message": "Database connection OK",
      "duration_ms": 12
    }
  }
}
```

**GET /metrics**
```json
{
  "counters": {
    "http.requests.total": 1250,
    "database.queries.total": 450
  },
  "gauges": {
    "memory.usage.bytes": 1073741824,
    "active.connections": 42
  },
  "histograms": {
    "request.duration.ms": {
      "count": 1250,
      "sum": 187500,
      "min": 10,
      "max": 2000,
      "avg": 150
    }
  }
}
```

### Handlers Customizados

```python
# Handler customizado
def custom_info_handler(query_params):
    return 200, {
        "application": "PySocketCommLib",
        "version": "1.0.0",
        "environment": "production"
    }

endpoints.add_custom_handler("/info", custom_info_handler)
```

## 📊 Integração com Prometheus

### Configuração do Prometheus

**prometheus.yml**
```yaml
scrape_configs:
  - job_name: 'pysocketcommlib'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    params:
      format: ['prometheus']
    scrape_interval: 15s
```

### Métricas Exportadas

```prometheus
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total 1250

# HELP memory_usage_bytes Current memory usage in bytes
# TYPE memory_usage_bytes gauge
memory_usage_bytes 1073741824

# HELP request_duration_ms Request duration in milliseconds
# TYPE request_duration_ms histogram
request_duration_ms_bucket{le="10"} 125
request_duration_ms_bucket{le="50"} 500
request_duration_ms_bucket{le="100"} 875
request_duration_ms_bucket{le="500"} 1200
request_duration_ms_bucket{le="+Inf"} 1250
request_duration_ms_sum 187500
request_duration_ms_count 1250
```

## 🔧 Exemplos Avançados

### Integração Completa

```python
from Monitoring import *
import time
import asyncio

class MonitoredApplication:
    def __init__(self):
        # Inicializa componentes de monitoramento
        self.metrics = MetricsCollector()
        self.tracker = PerformanceTracker()
        self.health = HealthChecker()
        self.readiness = ReadinessChecker()
        self.logger = StructuredLogger()
        self.endpoints = HealthEndpoints()
        
        # Configura integrações
        self.logger.set_metrics_integration(self.metrics)
        self.setup_health_checks()
        self.setup_readiness_checks()
    
    def setup_health_checks(self):
        """Configura verificações de saúde"""
        def database_check():
            # Implementa verificação de banco
            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database OK",
                duration_ms=10,
                timestamp=time.time()
            )
        
        self.health.register_check("database", database_check)
    
    def setup_readiness_checks(self):
        """Configura verificações de prontidão"""
        self.readiness.add_database_dependency(
            "main_db", "postgresql://localhost:5432/app"
        )
        self.readiness.add_http_dependency(
            "api", "https://api.example.com/health"
        )
    
    @property
    def performance_tracker(self):
        return self.tracker.track_performance
    
    def start_monitoring(self):
        """Inicia sistema de monitoramento"""
        self.health.start_background_checks(interval=30)
        self.endpoints.start()
        self.logger.info("Monitoramento iniciado", {
            "endpoints_url": self.endpoints.get_url()
        })
    
    def stop_monitoring(self):
        """Para sistema de monitoramento"""
        self.health.stop_background_checks()
        self.endpoints.stop()
        self.logger.info("Monitoramento parado")
    
    @performance_tracker
    def process_request(self, request_data):
        """Processa request com monitoramento automático"""
        with self.logger.context(request_id=request_data.get('id')):
            self.logger.info("Processando request", request_data)
            
            # Simula processamento
            time.sleep(0.1)
            
            # Registra métricas
            self.metrics.increment_counter('requests.processed')
            self.metrics.record_gauge('last_request_size', len(str(request_data)))
            
            self.logger.info("Request processado com sucesso")
            return {"status": "success"}
    
    async def async_operation(self):
        """Operação assíncrona monitorada"""
        async with self.tracker.track_async_performance('async_op'):
            self.logger.info("Iniciando operação assíncrona")
            await asyncio.sleep(0.05)
            self.metrics.increment_counter('async_operations')
            self.logger.info("Operação assíncrona concluída")

# Uso da aplicação monitorada
app = MonitoredApplication()
app.start_monitoring()

try:
    # Simula operações da aplicação
    for i in range(10):
        app.process_request({"id": f"req-{i}", "data": f"test-{i}"})
        time.sleep(0.1)
    
    # Operação assíncrona
    asyncio.run(app.async_operation())
    
    # Mantém aplicação rodando
    print(f"Monitoramento disponível em: {app.endpoints.get_url()}")
    print("Pressione Ctrl+C para parar...")
    
    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    app.stop_monitoring()
    print("Aplicação parada")
```

### Middleware para Flask/FastAPI

```python
# Flask Middleware
from flask import Flask, request, g
from Monitoring import MetricsCollector, PerformanceTracker, StructuredLogger
import time

app = Flask(__name__)
metrics = MetricsCollector()
tracker = PerformanceTracker()
logger = StructuredLogger()

@app.before_request
def before_request():
    g.start_time = time.time()
    g.request_context = logger.log_request_start(
        request.method, request.path, 
        user_id=request.headers.get('X-User-ID')
    )

@app.after_request
def after_request(response):
    duration = (time.time() - g.start_time) * 1000
    
    # Registra métricas
    metrics.increment_counter(f'http.requests.{response.status_code}')
    metrics.record_histogram('http.request.duration', duration)
    
    # Log estruturado
    logger.log_request_end(response.status_code, duration, len(response.data))
    
    return response

# FastAPI Middleware
from fastapi import FastAPI, Request
from fastapi.middleware.base import BaseHTTPMiddleware

class MonitoringMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.metrics = MetricsCollector()
        self.logger = StructuredLogger()
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log início do request
        self.logger.log_request_start(
            request.method, str(request.url.path)
        )
        
        # Processa request
        response = await call_next(request)
        
        # Calcula duração
        duration = (time.time() - start_time) * 1000
        
        # Registra métricas
        self.metrics.increment_counter(f'http.requests.{response.status_code}')
        self.metrics.record_histogram('http.request.duration', duration)
        
        # Log fim do request
        self.logger.log_request_end(response.status_code, duration, 0)
        
        return response

fastapi_app = FastAPI()
fastapi_app.add_middleware(MonitoringMiddleware)
```

## 🔍 Troubleshooting

### Problemas Comuns

**1. Endpoints HTTP não iniciam**
```python
# Verifica se a porta está disponível
import socket

def check_port(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    sock.close()
    return result != 0

if not check_port('localhost', 8080):
    print("Porta 8080 já está em uso")
```

**2. Métricas não aparecem**
```python
# Verifica se métricas estão sendo coletadas
metrics = MetricsCollector()
print("Métricas atuais:", metrics.get_metrics_summary())

# Força coleta de métricas do sistema
metrics.collect_system_metrics()
```

**3. Health checks falhando**
```python
# Debug de health checks
health = HealthChecker()
results = health.run_all_checks()

for name, result in results.items():
    if result.status != HealthStatus.HEALTHY:
        print(f"Health check '{name}' falhou: {result.message}")
```

**4. Logs não estruturados**
```python
# Verifica configuração do logger
logger = StructuredLogger()
logger.set_level(LogLevel.DEBUG)
logger.info("Teste de log estruturado", {"test": True})
```

### Performance

**Otimizações recomendadas:**

1. **Sampling de logs**: Use `logger.set_sampling_rate(0.1)` em produção
2. **Intervalo de health checks**: Configure intervalos apropriados para background checks
3. **Limpeza de métricas**: Implemente rotação de dados históricos se necessário
4. **Async operations**: Use versões assíncronas quando possível

### Monitoramento em Produção

**Configurações recomendadas:**

```python
# Configuração para produção
logger = StructuredLogger()
logger.set_level(LogLevel.INFO)  # Evita logs DEBUG
logger.set_sampling_rate(0.1)    # 10% dos logs

# Health checks menos frequentes
health.start_background_checks(interval=60)  # 1 minuto

# Endpoints em porta dedicada
endpoints = HealthEndpoints(host='0.0.0.0', port=9090)
```

## 📚 Referências

- [Prometheus Metrics Types](https://prometheus.io/docs/concepts/metric_types/)
- [Structured Logging Best Practices](https://engineering.grab.com/structured-logging)
- [Health Check Patterns](https://microservices.io/patterns/observability/health-check-api.html)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/)

---

**Desenvolvido para PySocketCommLib** 🚀

Para mais informações, consulte a documentação principal do projeto.