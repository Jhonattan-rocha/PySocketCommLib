"""Cache Metrics Module

Provides comprehensive metrics collection and reporting for cache operations.
"""

import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict, deque
from ..metrics.collector import MetricsCollector
from ..log_utils.structured_logger import StructuredLogger


@dataclass
class CacheStats:
    """Cache statistics data structure"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    errors: int = 0
    total_size: int = 0
    memory_usage: int = 0
    avg_access_time: float = 0.0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    
    def calculate_rates(self):
        """Calculate hit and miss rates"""
        total_requests = self.hits + self.misses
        if total_requests > 0:
            self.hit_rate = self.hits / total_requests
            self.miss_rate = self.misses / total_requests
        else:
            self.hit_rate = 0.0
            self.miss_rate = 0.0


class CacheMetrics:
    """Advanced cache metrics collector"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None,
                 logger: Optional[StructuredLogger] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logger or StructuredLogger()
        
        # Thread-safe statistics
        self._lock = threading.RLock()
        self._stats = CacheStats()
        
        # Time-series data for trends
        self._access_times = deque(maxlen=1000)
        self._hourly_stats = defaultdict(lambda: CacheStats())
        
        # Performance tracking
        self._operation_times = defaultdict(list)
        self._error_counts = defaultdict(int)
        
        # Start time for uptime calculation
        self._start_time = time.time()
        
    def record_hit(self, key: str, access_time: float = None):
        """Record a cache hit"""
        with self._lock:
            self._stats.hits += 1
            if access_time:
                self._access_times.append(access_time)
                self._update_avg_access_time()
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.hits')
            self.metrics_collector.record_histogram('cache.access_time', access_time or 0)
            
            self.logger.debug("Cache hit recorded", extra={
                'key': key,
                'access_time': access_time,
                'total_hits': self._stats.hits
            })
    
    def record_miss(self, key: str, access_time: float = None):
        """Record a cache miss"""
        with self._lock:
            self._stats.misses += 1
            if access_time:
                self._access_times.append(access_time)
                self._update_avg_access_time()
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.misses')
            self.metrics_collector.record_histogram('cache.access_time', access_time or 0)
            
            self.logger.debug("Cache miss recorded", extra={
                'key': key,
                'access_time': access_time,
                'total_misses': self._stats.misses
            })
    
    def record_set(self, key: str, size: int = 0, operation_time: float = None):
        """Record a cache set operation"""
        with self._lock:
            self._stats.sets += 1
            self._stats.total_size += size
            
            if operation_time:
                self._operation_times['set'].append(operation_time)
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.sets')
            self.metrics_collector.set_gauge('cache.total_size', self._stats.total_size)
            if operation_time:
                self.metrics_collector.record_histogram('cache.set_time', operation_time)
            
            self.logger.debug("Cache set recorded", extra={
                'key': key,
                'size': size,
                'operation_time': operation_time,
                'total_sets': self._stats.sets
            })
    
    def record_delete(self, key: str, size: int = 0, operation_time: float = None):
        """Record a cache delete operation"""
        with self._lock:
            self._stats.deletes += 1
            self._stats.total_size = max(0, self._stats.total_size - size)
            
            if operation_time:
                self._operation_times['delete'].append(operation_time)
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.deletes')
            self.metrics_collector.set_gauge('cache.total_size', self._stats.total_size)
            if operation_time:
                self.metrics_collector.record_histogram('cache.delete_time', operation_time)
            
            self.logger.debug("Cache delete recorded", extra={
                'key': key,
                'size': size,
                'operation_time': operation_time,
                'total_deletes': self._stats.deletes
            })
    
    def record_eviction(self, key: str, reason: str = "size_limit"):
        """Record a cache eviction"""
        with self._lock:
            self._stats.evictions += 1
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.evictions')
            self.metrics_collector.increment_counter(f'cache.evictions.{reason}')
            
            self.logger.info("Cache eviction recorded", extra={
                'key': key,
                'reason': reason,
                'total_evictions': self._stats.evictions
            })
    
    def record_error(self, operation: str, error: Exception = None, key: str = None):
        """Record a cache error"""
        with self._lock:
            self._stats.errors += 1
            self._error_counts[operation] += 1
            
            # Update metrics collector
            self.metrics_collector.increment_counter('cache.errors')
            self.metrics_collector.increment_counter(f'cache.errors.{operation}')
            
            self.logger.error("Cache error recorded", extra={
                'operation': operation,
                'error': str(error),
                'error_type': type(error).__name__,
                'key': key,
                'total_errors': self._stats.errors
            })
    
    def update_memory_usage(self, memory_bytes: int):
        """Update memory usage metrics"""
        with self._lock:
            self._stats.memory_usage = memory_bytes
            
            # Update metrics collector
            self.metrics_collector.set_gauge('cache.memory_usage_bytes', memory_bytes)
            self.metrics_collector.set_gauge('cache.memory_usage_mb', memory_bytes / 1024 / 1024)
    
    def _update_avg_access_time(self):
        """Update average access time"""
        if self._access_times:
            self._stats.avg_access_time = sum(self._access_times) / len(self._access_times)
    
    def get_stats(self) -> CacheStats:
        """Get current cache statistics"""
        with self._lock:
            stats = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions,
                errors=self._stats.errors,
                total_size=self._stats.total_size,
                memory_usage=self._stats.memory_usage,
                avg_access_time=self._stats.avg_access_time
            )
            stats.calculate_rates()
            return stats
    
    def get_detailed_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics including performance data"""
        with self._lock:
            stats = self.get_stats()
            
            # Calculate operation performance
            operation_stats = {}
            for op, times in self._operation_times.items():
                if times:
                    operation_stats[op] = {
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'count': len(times)
                    }
            
            return {
                'basic_stats': {
                    'hits': stats.hits,
                    'misses': stats.misses,
                    'sets': stats.sets,
                    'deletes': stats.deletes,
                    'evictions': stats.evictions,
                    'errors': stats.errors,
                    'hit_rate': stats.hit_rate,
                    'miss_rate': stats.miss_rate
                },
                'performance': {
                    'avg_access_time': stats.avg_access_time,
                    'operation_stats': operation_stats
                },
                'memory': {
                    'total_size': stats.total_size,
                    'memory_usage_bytes': stats.memory_usage,
                    'memory_usage_mb': stats.memory_usage / 1024 / 1024
                },
                'errors': dict(self._error_counts),
                'uptime_seconds': time.time() - self._start_time
            }
    
    def reset_stats(self):
        """Reset all statistics"""
        with self._lock:
            self._stats = CacheStats()
            self._access_times.clear()
            self._hourly_stats.clear()
            self._operation_times.clear()
            self._error_counts.clear()
            self._start_time = time.time()
            
            self.logger.info("Cache statistics reset")
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export metrics in a format suitable for external monitoring systems"""
        stats = self.get_detailed_metrics()
        
        # Flatten metrics for easier consumption
        flattened = {
            'cache_hits_total': stats['basic_stats']['hits'],
            'cache_misses_total': stats['basic_stats']['misses'],
            'cache_sets_total': stats['basic_stats']['sets'],
            'cache_deletes_total': stats['basic_stats']['deletes'],
            'cache_evictions_total': stats['basic_stats']['evictions'],
            'cache_errors_total': stats['basic_stats']['errors'],
            'cache_hit_rate': stats['basic_stats']['hit_rate'],
            'cache_miss_rate': stats['basic_stats']['miss_rate'],
            'cache_avg_access_time_seconds': stats['performance']['avg_access_time'],
            'cache_total_size': stats['memory']['total_size'],
            'cache_memory_usage_bytes': stats['memory']['memory_usage_bytes'],
            'cache_uptime_seconds': stats['uptime_seconds']
        }
        
        # Add operation-specific metrics
        for op, op_stats in stats['performance']['operation_stats'].items():
            flattened[f'cache_{op}_avg_time_seconds'] = op_stats['avg_time']
            flattened[f'cache_{op}_min_time_seconds'] = op_stats['min_time']
            flattened[f'cache_{op}_max_time_seconds'] = op_stats['max_time']
            flattened[f'cache_{op}_count'] = op_stats['count']
        
        # Add error-specific metrics
        for error_type, count in stats['errors'].items():
            flattened[f'cache_errors_{error_type}_total'] = count
        
        return flattened
    
    def log_periodic_summary(self):
        """Log a periodic summary of cache performance"""
        stats = self.get_detailed_metrics()
        
        self.logger.info("Cache performance summary", extra={
            'hit_rate': f"{stats['basic_stats']['hit_rate']:.2%}",
            'total_requests': stats['basic_stats']['hits'] + stats['basic_stats']['misses'],
            'avg_access_time_ms': f"{stats['performance']['avg_access_time'] * 1000:.2f}",
            'memory_usage_mb': f"{stats['memory']['memory_usage_mb']:.2f}",
            'total_errors': stats['basic_stats']['errors'],
            'uptime_hours': f"{stats['uptime_seconds'] / 3600:.1f}"
        })