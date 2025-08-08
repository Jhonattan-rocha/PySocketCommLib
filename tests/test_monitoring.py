"""Tests for Monitoring System

Testes unitários para o sistema de monitoramento:
- MetricsCollector
- PerformanceTracker
- HealthChecker
- ReadinessChecker
- StructuredLogger
- HealthEndpoints
"""

import unittest
import time
import threading
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import sys
import os

# Adiciona o diretório pai ao path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Monitoring.metrics.collector import MetricsCollector
from Monitoring.metrics.performance import PerformanceTracker
from Monitoring.health.checker import HealthChecker, HealthStatus, HealthCheckResult
from Monitoring.health.readiness import ReadinessChecker, ReadinessStatus, ReadinessCheckResult
from Monitoring.log_utils.structured_logger import StructuredLogger, LogLevel
from Monitoring.endpoints.health_endpoints import HealthEndpoints


class TestMetricsCollector(unittest.TestCase):
    """Testes para MetricsCollector"""
    
    def setUp(self):
        self.collector = MetricsCollector()
    
    def test_singleton_pattern(self):
        """Testa se MetricsCollector é singleton"""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()
        self.assertIs(collector1, collector2)
    
    def test_increment_counter(self):
        """Testa incremento de contador"""
        self.collector.increment_counter('test.counter')
        self.collector.increment_counter('test.counter', 5)
        
        metrics = self.collector.get_metrics_summary()
        self.assertEqual(metrics['counters']['test.counter'], 6)
    
    def test_record_gauge(self):
        """Testa registro de gauge"""
        self.collector.record_gauge('test.gauge', 42.5)
        self.collector.record_gauge('test.gauge', 37.8)
        
        metrics = self.collector.get_metrics_summary()
        self.assertEqual(metrics['gauges']['test.gauge'], 37.8)
    
    def test_record_histogram(self):
        """Testa registro de histograma"""
        values = [10, 20, 30, 40, 50]
        for value in values:
            self.collector.record_histogram('test.histogram', value)
        
        metrics = self.collector.get_metrics_summary()
        histogram = metrics['histograms']['test.histogram']
        
        self.assertEqual(histogram['count'], 5)
        self.assertEqual(histogram['sum'], 150)
        self.assertEqual(histogram['min'], 10)
        self.assertEqual(histogram['max'], 50)
        self.assertEqual(histogram['avg'], 30)
    
    def test_system_metrics_collection(self):
        """Testa coleta de métricas do sistema"""
        self.collector.collect_system_metrics()
        metrics = self.collector.get_metrics_summary()
        
        # Verifica se métricas do sistema foram coletadas
        self.assertIn('system.cpu_percent', metrics['gauges'])
        self.assertIn('system.memory_percent', metrics['gauges'])
        self.assertIn('system.disk_percent', metrics['gauges'])
    
    def test_prometheus_export(self):
        """Testa exportação para formato Prometheus"""
        self.collector.increment_counter('http_requests_total', 10)
        self.collector.record_gauge('memory_usage_bytes', 1024)
        
        prometheus_output = self.collector.export_prometheus()
        
        self.assertIn('http_requests_total 10', prometheus_output)
        self.assertIn('memory_usage_bytes 1024', prometheus_output)
        self.assertIn('# TYPE http_requests_total counter', prometheus_output)
        self.assertIn('# TYPE memory_usage_bytes gauge', prometheus_output)


class TestPerformanceTracker(unittest.TestCase):
    """Testes para PerformanceTracker"""
    
    def setUp(self):
        self.tracker = PerformanceTracker()
        self.collector = MetricsCollector()
        self.tracker.metrics_collector = self.collector
    
    def test_context_manager_tracking(self):
        """Testa tracking com context manager"""
        with self.tracker.measure_time('test_operation'):
            time.sleep(0.1)
        
        metrics = self.collector.get_metrics_summary()
        # Verifica se alguma métrica de duração foi registrada
        histogram_keys = list(metrics['histograms'].keys())
        duration_metrics = [k for k in histogram_keys if 'duration' in k or 'test_operation' in k]
        self.assertTrue(len(duration_metrics) > 0, f"No duration metrics found in {histogram_keys}")
    
    def test_decorator_tracking(self):
        """Testa tracking com decorator"""
        @self.tracker.track_performance
        def test_function():
            time.sleep(0.05)
            return "result"
        
        result = test_function()
        self.assertEqual(result, "result")
        
        metrics = self.collector.get_metrics_summary()
        # Verifica se alguma métrica de performance foi registrada
        histogram_keys = list(metrics['histograms'].keys())
        performance_metrics = [k for k in histogram_keys if 'performance' in k or 'test_function' in k]
        self.assertGreater(len(performance_metrics), 0, f"No performance metrics found in {histogram_keys}")
    
    def test_async_tracking(self):
        """Testa tracking assíncrono"""
        async def async_test():
            with self.tracker.track_async_performance('async_operation'):
                await asyncio.sleep(0.05)
        
        asyncio.run(async_test())
        
        metrics = self.collector.get_metrics_summary()
        self.assertIn('performance.async_operation.duration', metrics['histograms'])
    
    def test_error_tracking(self):
        """Testa tracking de erros"""
        try:
            with self.tracker.measure_time('error_operation'):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        metrics = self.collector.get_metrics_summary()
        # Verifica se métricas de erro foram registradas
        counter_keys = list(metrics['counters'].keys())
        error_metrics = [k for k in counter_keys if 'error' in k]
        self.assertTrue(len(error_metrics) > 0, f"No error metrics found in {counter_keys}")


class TestHealthChecker(unittest.TestCase):
    """Testes para HealthChecker"""
    
    def setUp(self):
        self.checker = HealthChecker()
    
    def test_register_custom_check(self):
        """Testa registro de verificação personalizada"""
        def custom_check():
            return HealthCheckResult(
                name="custom",
                status=HealthStatus.HEALTHY,
                message="Custom check OK",
                duration_ms=10,
                timestamp=time.time()
            )
        
        self.checker.register_check("custom", custom_check)
        result = self.checker.run_check("custom")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.message, "Custom check OK")
    
    def test_run_all_checks(self):
        """Testa execução de todas as verificações"""
        results = self.checker.run_all_checks()
        
        # Verifica se as verificações padrão foram executadas
        self.assertIn('system_resources', results)
        self.assertIn('disk_space', results)
        self.assertIn('memory_usage', results)
    
    def test_overall_status_calculation(self):
        """Testa cálculo do status geral"""
        # Adiciona verificação que sempre falha
        def failing_check():
            return HealthCheckResult(
                name="failing",
                status=HealthStatus.UNHEALTHY,
                message="Always fails",
                duration_ms=0,
                timestamp=time.time()
            )
        
        self.checker.register_check("failing", failing_check)
        self.checker.run_all_checks()
        
        overall_status = self.checker.get_overall_status()
        self.assertEqual(overall_status, HealthStatus.UNHEALTHY)
    
    def test_background_checks(self):
        """Testa verificações em background"""
        self.checker.start_background_checks(interval=1)
        time.sleep(1.5)  # Aguarda pelo menos uma execução
        self.checker.stop_background_checks()
        
        # Verifica se as verificações foram executadas
        summary = self.checker.get_health_summary()
        self.assertGreater(len(summary['checks']), 0)


class TestReadinessChecker(unittest.TestCase):
    """Testes para ReadinessChecker"""
    
    def setUp(self):
        self.checker = ReadinessChecker()
    
    def test_add_tcp_dependency(self):
        """Testa adição de dependência TCP"""
        self.checker.add_tcp_dependency(
            name="test_service",
            host="localhost",
            port=80,
            timeout=5
        )
        
        # Verifica se a dependência foi adicionada
        self.assertIn('tcp_test_service', self.checker._dependencies)
        self.assertIn('tcp_test_service', self.checker._checks)
    
    def test_add_http_dependency(self):
        """Testa adição de dependência HTTP"""
        self.checker.add_http_dependency(
            name="api",
            url="https://httpbin.org/status/200",
            expected_status=200,
            timeout=10
        )
        
        # Verifica se a dependência foi adicionada
        self.assertIn('http_api', self.checker._dependencies)
        self.assertIn('http_api', self.checker._checks)
    
    @patch('socket.socket')
    def test_tcp_dependency_check_success(self, mock_socket):
        """Testa verificação TCP bem-sucedida"""
        # Mock do socket para simular conexão bem-sucedida
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        self.checker.add_tcp_dependency("test", "localhost", 80)
        result = self.checker.run_check("tcp_test")
        
        self.assertEqual(result.status, ReadinessStatus.READY)
    
    @patch('socket.socket')
    def test_tcp_dependency_check_failure(self, mock_socket):
        """Testa verificação TCP com falha"""
        # Mock do socket para simular falha de conexão
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 1  # Erro de conexão
        mock_socket.return_value = mock_sock
        
        self.checker.add_tcp_dependency("test", "localhost", 80)
        result = self.checker.run_check("tcp_test")
        
        self.assertEqual(result.status, ReadinessStatus.NOT_READY)
    
    def test_is_ready_calculation(self):
        """Testa cálculo de prontidão"""
        # Adiciona verificação que sempre passa
        def ready_check():
            return ReadinessCheckResult(
                name="ready",
                status=ReadinessStatus.READY,
                message="Ready",
                duration_ms=0,
                timestamp=time.time()
            )
        
        self.checker.register_check("ready", ready_check)
        
        # Executa verificações
        self.checker.run_all_checks()
        
        # Verifica se está pronto
        self.assertTrue(self.checker.is_ready())


class TestStructuredLogger(unittest.TestCase):
    """Testes para StructuredLogger"""
    
    def setUp(self):
        self.logger = StructuredLogger()
        # Captura saída do logger
        self.log_output = StringIO()
        handler = self.logger._logger.handlers[0]
        handler.stream = self.log_output
    
    def test_singleton_pattern(self):
        """Testa se StructuredLogger é singleton"""
        logger1 = StructuredLogger()
        logger2 = StructuredLogger()
        self.assertIs(logger1, logger2)
    
    def test_structured_logging(self):
        """Testa logging estruturado"""
        self.logger.info("Test message", {"key": "value"})
        
        log_content = self.log_output.getvalue()
        self.assertIn("Test message", log_content)
        
        # Verifica se é JSON válido
        try:
            log_data = json.loads(log_content.strip())
            self.assertEqual(log_data['level'], 'INFO')
            self.assertEqual(log_data['message'], 'Test message')
            self.assertEqual(log_data['extra']['key'], 'value')
        except json.JSONDecodeError:
            self.fail("Log output is not valid JSON")
    
    def test_context_management(self):
        """Testa gerenciamento de contexto"""
        with self.logger.context(user_id="123", operation="test"):
            self.logger.info("Context test")
        
        log_content = self.log_output.getvalue()
        log_data = json.loads(log_content.strip())
        
        self.assertIn('context', log_data)
        self.assertEqual(log_data['context']['user_id'], '123')
        self.assertEqual(log_data['context']['operation'], 'test')
    
    def test_exception_logging(self):
        """Testa logging de exceções"""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            self.logger.exception("Exception occurred", e)
        
        log_content = self.log_output.getvalue()
        log_data = json.loads(log_content.strip())
        
        self.assertIn('exception', log_data)
        self.assertEqual(log_data['exception']['type'], 'ValueError')
        self.assertEqual(log_data['exception']['message'], 'Test exception')
    
    def test_request_logging(self):
        """Testa logging de requisições"""
        context = self.logger.log_request_start("GET", "/api/test", user_id="user123")
        self.logger.log_request_end(200, 150.5, 1024)
        
        log_content = self.log_output.getvalue()
        lines = log_content.strip().split('\n')
        
        # Verifica log de início
        start_log = json.loads(lines[0])
        self.assertIn('Request started', start_log['message'])
        self.assertEqual(start_log['extra']['http_method'], 'GET')
        
        # Verifica log de fim
        end_log = json.loads(lines[1])
        self.assertIn('Request completed', end_log['message'])
        self.assertEqual(end_log['extra']['http_status_code'], 200)


class TestHealthEndpoints(unittest.TestCase):
    """Testes para HealthEndpoints"""
    
    def setUp(self):
        self.endpoints = HealthEndpoints(host='localhost', port=0)  # Porta 0 para auto-seleção
    
    def tearDown(self):
        if self.endpoints.is_running():
            self.endpoints.stop()
    
    def test_endpoint_initialization(self):
        """Testa inicialização dos endpoints"""
        self.assertIsNotNone(self.endpoints.health_checker)
        self.assertIsNotNone(self.endpoints.readiness_checker)
        self.assertIsNotNone(self.endpoints.metrics_collector)
    
    def test_custom_handler_registration(self):
        """Testa registro de handler personalizado"""
        def custom_handler(query_params):
            return 200, {"message": "Custom endpoint"}
        
        self.endpoints.add_custom_handler("/custom", custom_handler)
        self.assertIn("/custom", self.endpoints.custom_handlers)
    
    def test_server_start_stop(self):
        """Testa início e parada do servidor"""
        self.endpoints.start()
        self.assertTrue(self.endpoints.is_running())
        
        self.endpoints.stop()
        self.assertFalse(self.endpoints.is_running())
    
    def test_url_generation(self):
        """Testa geração de URLs"""
        base_url = self.endpoints.get_url()
        health_url = self.endpoints.get_url('/health')
        
        self.assertTrue(base_url.startswith('http://'))
        self.assertTrue(health_url.endswith('/health'))


class TestMonitoringIntegration(unittest.TestCase):
    """Testes de integração do sistema de monitoramento"""
    
    def setUp(self):
        self.collector = MetricsCollector()
        self.tracker = PerformanceTracker()
        self.health_checker = HealthChecker()
        self.logger = StructuredLogger()
        
        # Integra componentes
        self.logger.set_metrics_integration(self.collector)
    
    def test_metrics_logger_integration(self):
        """Testa integração entre métricas e logger"""
        # Faz alguns logs
        self.logger.info("Test info")
        self.logger.error("Test error")
        self.logger.warning("Test warning")
        
        # Verifica se métricas foram registradas
        metrics = self.collector.get_metrics_summary()
        self.assertIn('logs.info', metrics['counters'])
        self.assertIn('logs.error', metrics['counters'])
        self.assertIn('logs.warning', metrics['counters'])
    
    def test_performance_metrics_integration(self):
        """Testa integração entre performance tracker e métricas"""
        with self.tracker.track_performance('integration_test'):
            time.sleep(0.01)
        
        metrics = self.collector.get_metrics_summary()
        self.assertIn('performance.integration_test.duration', metrics['histograms'])
        self.assertIn('performance.integration_test.count', metrics['counters'])
    
    def test_health_check_with_metrics(self):
        """Testa health check com coleta de métricas"""
        # Executa health checks
        self.health_checker.run_all_checks()
        
        # Verifica se health checks foram executados
        summary = self.health_checker.get_health_summary()
        self.assertGreater(len(summary['checks']), 0)
        
        # Verifica status geral
        overall_status = self.health_checker.get_overall_status()
        self.assertIn(overall_status, [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY])


if __name__ == '__main__':
    # Configura logging para testes
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Executa testes
    unittest.main(verbosity=2)