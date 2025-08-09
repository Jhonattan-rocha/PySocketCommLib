"""Cache Manager - Main Cache System Coordinator

Provides a unified interface for caching operations with support for multiple backends,
strategies, and comprehensive monitoring.
"""

import time
import asyncio
import threading
from typing import Any, Optional, Dict, List, Union, Callable, Type
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

from .config import CacheConfig, CacheBackend, CacheStrategy
from .backends.memory import MemoryBackend
from .backends.redis import RedisBackend
from .metrics import CacheMetrics
from ..log_utils.structured_logger import StructuredLogger
from ..metrics.collector import MetricsCollector
from ..metrics.performance import PerformanceTracker


class CacheManager:
    """Main cache manager that coordinates all caching operations"""
    
    def __init__(self, 
                 config: Optional[CacheConfig] = None,
                 metrics_collector: Optional[MetricsCollector] = None,
                 performance_tracker: Optional[PerformanceTracker] = None,
                 logger: Optional[StructuredLogger] = None):
        
        # Use default config if none provided
        self.config = config or CacheConfig()
        
        # Initialize monitoring components
        self.metrics_collector = metrics_collector
        self.performance_tracker = performance_tracker
        self.logger = logger or StructuredLogger()
        
        # Initialize cache metrics
        self.cache_metrics = CacheMetrics(
            metrics_collector=self.metrics_collector,
            logger=self.logger
        )
        
        # Initialize backend
        self.backend = self._create_backend()
        
        # Cache state
        self._initialized = True
        self._closed = False
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Performance tracking
        self._operation_stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'avg_response_time': 0.0
        }
        
        self.logger.info("Cache manager initialized", extra={
            'backend': self.config.backend.value,
            'strategy': self.config.strategy.value,
            'max_size': self.config.max_size,
            'default_ttl': self.config.default_ttl
        })
    
    def _create_backend(self):
        """Create the appropriate cache backend"""
        backend_map = {
            CacheBackend.MEMORY: MemoryBackend,
            CacheBackend.REDIS: RedisBackend
        }
        
        backend_class = backend_map.get(self.config.backend)
        if not backend_class:
            raise ValueError(f"Unsupported cache backend: {self.config.backend}")
        
        return backend_class(self.config, self.cache_metrics)
    
    def _ensure_not_closed(self):
        """Ensure the cache manager is not closed"""
        if self._closed:
            raise RuntimeError("Cache manager has been closed")
    
    def _track_operation(self, operation_name: str, start_time: float, success: bool):
        """Track operation performance and statistics"""
        operation_time = time.time() - start_time
        
        with self._lock:
            self._operation_stats['total_operations'] += 1
            if success:
                self._operation_stats['successful_operations'] += 1
            else:
                self._operation_stats['failed_operations'] += 1
            
            # Update average response time
            total_ops = self._operation_stats['total_operations']
            current_avg = self._operation_stats['avg_response_time']
            self._operation_stats['avg_response_time'] = (
                (current_avg * (total_ops - 1) + operation_time) / total_ops
            )
        
        # Track with performance tracker if available
        if self.performance_tracker:
            with self.performance_tracker.measure_time(f"cache.{operation_name}"):
                pass  # Time already measured, just record it
    
    # Core cache operations
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the cache"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            value = self.backend.get(key)
            success = True
            
            if value is None:
                self.logger.debug("Cache miss", extra={'key': key})
                return default
            else:
                self.logger.debug("Cache hit", extra={'key': key})
                return value
                
        except Exception as e:
            success = False
            self.logger.error("Cache get error", extra={
                'key': key,
                'error': str(e)
            })
            return default
        finally:
            self._track_operation('get', start_time, success)
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            success = self.backend.set(key, value, ttl)
            
            if success:
                self.logger.debug("Cache set successful", extra={
                    'key': key,
                    'ttl': ttl
                })
            else:
                self.logger.warning("Cache set failed", extra={'key': key})
            
            return success
            
        except Exception as e:
            success = False
            self.logger.error("Cache set error", extra={
                'key': key,
                'error': str(e)
            })
            return False
        finally:
            self._track_operation('set', start_time, success)
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            success = self.backend.delete(key)
            
            if success:
                self.logger.debug("Cache delete successful", extra={'key': key})
            else:
                self.logger.debug("Cache delete failed (key not found)", extra={'key': key})
            
            return success
            
        except Exception as e:
            success = False
            self.logger.error("Cache delete error", extra={
                'key': key,
                'error': str(e)
            })
            return False
        finally:
            self._track_operation('delete', start_time, success)
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            exists = self.backend.exists(key)
            success = True
            return exists
            
        except Exception as e:
            success = False
            self.logger.error("Cache exists error", extra={
                'key': key,
                'error': str(e)
            })
            return False
        finally:
            self._track_operation('exists', start_time, success)
    
    def clear(self) -> bool:
        """Clear all entries from the cache"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            success = self.backend.clear()
            
            if success:
                self.logger.info("Cache cleared successfully")
            else:
                self.logger.warning("Cache clear failed")
            
            return success
            
        except Exception as e:
            success = False
            self.logger.error("Cache clear error", extra={'error': str(e)})
            return False
        finally:
            self._track_operation('clear', start_time, success)
    
    # Async operations
    async def get_async(self, key: str, default: Any = None) -> Any:
        """Async version of get"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'get_async'):
                value = await self.backend.get_async(key)
            else:
                # Fallback to sync version in thread pool
                loop = asyncio.get_event_loop()
                value = await loop.run_in_executor(None, self.backend.get, key)
            
            success = True
            return value if value is not None else default
            
        except Exception as e:
            success = False
            self.logger.error("Async cache get error", extra={
                'key': key,
                'error': str(e)
            })
            return default
        finally:
            self._track_operation('get_async', start_time, success)
    
    async def set_async(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Async version of set"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'set_async'):
                success = await self.backend.set_async(key, value, ttl)
            else:
                # Fallback to sync version in thread pool
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, self.backend.set, key, value, ttl)
            
            return success
            
        except Exception as e:
            success = False
            self.logger.error("Async cache set error", extra={
                'key': key,
                'error': str(e)
            })
            return False
        finally:
            self._track_operation('set_async', start_time, success)
    
    async def delete_async(self, key: str) -> bool:
        """Async version of delete"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'delete_async'):
                success = await self.backend.delete_async(key)
            else:
                # Fallback to sync version in thread pool
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(None, self.backend.delete, key)
            
            return success
            
        except Exception as e:
            success = False
            self.logger.error("Async cache delete error", extra={
                'key': key,
                'error': str(e)
            })
            return False
        finally:
            self._track_operation('delete_async', start_time, success)
    
    # Batch operations
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'get_many'):
                result = self.backend.get_many(keys)
            else:
                # Fallback to individual gets
                result = {}
                for key in keys:
                    value = self.backend.get(key)
                    if value is not None:
                        result[key] = value
            
            success = True
            self.logger.debug("Batch get completed", extra={
                'requested_keys': len(keys),
                'found_keys': len(result)
            })
            
            return result
            
        except Exception as e:
            success = False
            self.logger.error("Batch get error", extra={
                'keys': keys,
                'error': str(e)
            })
            return {}
        finally:
            self._track_operation('get_many', start_time, success)
    
    def set_many(self, items: Dict[str, Any], ttl: Optional[float] = None) -> Dict[str, bool]:
        """Set multiple values at once"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'set_many'):
                result = self.backend.set_many(items, ttl)
            else:
                # Fallback to individual sets
                result = {}
                for key, value in items.items():
                    result[key] = self.backend.set(key, value, ttl)
            
            success = True
            successful_sets = sum(1 for success in result.values() if success)
            
            self.logger.debug("Batch set completed", extra={
                'total_items': len(items),
                'successful_sets': successful_sets
            })
            
            return result
            
        except Exception as e:
            success = False
            self.logger.error("Batch set error", extra={
                'items_count': len(items),
                'error': str(e)
            })
            return {key: False for key in items.keys()}
        finally:
            self._track_operation('set_many', start_time, success)
    
    def delete_many(self, keys: List[str]) -> Dict[str, bool]:
        """Delete multiple values at once"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'delete_many'):
                result = self.backend.delete_many(keys)
            else:
                # Fallback to individual deletes
                result = {}
                for key in keys:
                    result[key] = self.backend.delete(key)
            
            success = True
            successful_deletes = sum(1 for success in result.values() if success)
            
            self.logger.debug("Batch delete completed", extra={
                'total_keys': len(keys),
                'successful_deletes': successful_deletes
            })
            
            return result
            
        except Exception as e:
            success = False
            self.logger.error("Batch delete error", extra={
                'keys': keys,
                'error': str(e)
            })
            return {key: False for key in keys}
        finally:
            self._track_operation('delete_many', start_time, success)
    
    # Cache warming
    def warm_cache(self, data_loader: Callable[[], Dict[str, Any]], 
                   ttl: Optional[float] = None) -> Dict[str, bool]:
        """Warm the cache with data from a loader function"""
        self._ensure_not_closed()
        start_time = time.time()
        
        try:
            if hasattr(self.backend, 'warm_cache'):
                result = self.backend.warm_cache(data_loader, ttl)
            else:
                # Fallback implementation
                data = data_loader()
                result = self.set_many(data, ttl)
            
            success = True
            successful_loads = sum(1 for success in result.values() if success)
            
            self.logger.info("Cache warming completed", extra={
                'total_items': len(result),
                'successful_loads': successful_loads
            })
            
            return result
            
        except Exception as e:
            success = False
            self.logger.error("Cache warming error", extra={'error': str(e)})
            return {}
        finally:
            self._track_operation('warm_cache', start_time, success)
    
    # Statistics and monitoring
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            backend_stats = self.backend.get_stats()
            
            manager_stats = {
                'manager': {
                    'initialized': self._initialized,
                    'closed': self._closed,
                    'config': {
                        'backend': self.config.backend.value,
                        'strategy': self.config.strategy.value,
                        'max_size': self.config.max_size,
                        'default_ttl': self.config.default_ttl
                    },
                    'operations': self._operation_stats.copy()
                }
            }
            
            return {**backend_stats, **manager_stats}
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_size(self) -> int:
        """Get current cache size"""
        try:
            return self.backend.size()
        except Exception:
            return 0
    
    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        try:
            return self.backend.memory_usage()
        except Exception:
            return 0
    
    def get_keys(self) -> List[str]:
        """Get all keys in the cache"""
        try:
            return self.backend.keys()
        except Exception:
            return []
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate"""
        try:
            return self.cache_metrics.get_hit_rate()
        except Exception:
            return 0.0
    
    # Health check
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        try:
            backend_health = self.backend.health_check()
            
            manager_health = {
                'manager_healthy': not self._closed and self._initialized,
                'total_operations': self._operation_stats['total_operations'],
                'success_rate': (
                    self._operation_stats['successful_operations'] / 
                    max(self._operation_stats['total_operations'], 1)
                ),
                'avg_response_time': self._operation_stats['avg_response_time']
            }
            
            overall_healthy = (
                backend_health.get('healthy', False) and 
                manager_health['manager_healthy']
            )
            
            return {
                'healthy': overall_healthy,
                'backend': backend_health,
                'manager': manager_health,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': time.time()
            }
    
    # Context manager support
    @contextmanager
    def transaction(self):
        """Context manager for cache transactions (if supported by backend)"""
        # This is a placeholder for transaction support
        # Actual implementation would depend on backend capabilities
        try:
            yield self
        except Exception as e:
            self.logger.error("Cache transaction error", extra={'error': str(e)})
            raise
    
    # Lifecycle management
    def close(self):
        """Close the cache manager and cleanup resources"""
        if self._closed:
            return
        
        try:
            if hasattr(self.backend, '__exit__'):
                self.backend.__exit__(None, None, None)
            
            self._closed = True
            self.logger.info("Cache manager closed")
            
        except Exception as e:
            self.logger.error("Error closing cache manager", extra={'error': str(e)})
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Destructor"""
        try:
            if not self._closed:
                self.close()
        except Exception:
            pass  # Ignore errors during cleanup
    
    # Convenience methods
    def get_or_set(self, key: str, value_factory: Callable[[], Any], 
                   ttl: Optional[float] = None) -> Any:
        """Get a value or set it if it doesn't exist"""
        value = self.get(key)
        if value is None:
            value = value_factory()
            self.set(key, value, ttl)
        return value
    
    async def get_or_set_async(self, key: str, value_factory: Callable[[], Any], 
                              ttl: Optional[float] = None) -> Any:
        """Async version of get_or_set"""
        value = await self.get_async(key)
        if value is None:
            if asyncio.iscoroutinefunction(value_factory):
                value = await value_factory()
            else:
                value = value_factory()
            await self.set_async(key, value, ttl)
        return value
    
    def increment(self, key: str, amount: int = 1, default: int = 0, 
                  ttl: Optional[float] = None) -> int:
        """Increment a numeric value (with Redis backend optimization)"""
        if hasattr(self.backend, 'increment'):
            # Use Redis native increment if available
            result = self.backend.increment(key, amount)
            if result is not None:
                return result
        
        # Fallback to get-modify-set
        current = self.get(key, default)
        if not isinstance(current, (int, float)):
            current = default
        
        new_value = int(current) + amount
        self.set(key, new_value, ttl)
        return new_value
    
    def decrement(self, key: str, amount: int = 1, default: int = 0, 
                  ttl: Optional[float] = None) -> int:
        """Decrement a numeric value (with Redis backend optimization)"""
        if hasattr(self.backend, 'decrement'):
            # Use Redis native decrement if available
            result = self.backend.decrement(key, amount)
            if result is not None:
                return result
        
        # Fallback to get-modify-set
        current = self.get(key, default)
        if not isinstance(current, (int, float)):
            current = default
        
        new_value = int(current) - amount
        self.set(key, new_value, ttl)
        return new_value