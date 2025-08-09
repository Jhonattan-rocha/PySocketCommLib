"""Memory Backend for Cache System

Provides in-memory caching with pluggable strategies and comprehensive monitoring.
"""

import time
import threading
import asyncio
from typing import Any, Optional, Dict, List, Union, Callable
from concurrent.futures import ThreadPoolExecutor

from ..config import CacheConfig, CacheStrategy as StrategyType
from ..strategies.lru import LRUCache
from ..strategies.ttl import TTLCache
from ..strategies.fifo import FIFOCache
from ..strategies.lfu import LFUCache
from ..strategies.base import CacheStrategy
from ..metrics import CacheMetrics
from ..serializers import SerializerFactory
from ...log_utils.structured_logger import StructuredLogger


class MemoryBackend:
    """Memory-based cache backend with pluggable strategies"""
    
    def __init__(self, config: CacheConfig, metrics: Optional[CacheMetrics] = None):
        self.config = config
        self.metrics = metrics or CacheMetrics()
        
        # Initialize serializer
        self.serializer = SerializerFactory.create_serializer(
            config.serialization_format,
            enable_compression=config.enable_compression,
            compression_threshold=config.compression_threshold
        )
        
        # Initialize cache strategy
        self.strategy = self._create_strategy()
        
        # Thread pool for async operations
        self._thread_pool = ThreadPoolExecutor(
            max_workers=config.max_concurrent_operations,
            thread_name_prefix="cache-worker"
        )
        
        # Background cleanup
        self._cleanup_interval = config.cleanup_interval
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = 0
        self._circuit_breaker_open = False
        
        # Performance tracking
        self._operation_times = []
        self._max_operation_history = 1000
        
        if config.enable_background_cleanup:
            self.start_background_cleanup()
    
    def _create_strategy(self) -> CacheStrategy:
        """Create cache strategy based on configuration"""
        strategy_map = {
            StrategyType.LRU: LRUCache,
            StrategyType.TTL: TTLCache,
            StrategyType.FIFO: FIFOCache,
            StrategyType.LFU: LFUCache
        }
        
        strategy_class = strategy_map.get(self.config.strategy)
        if not strategy_class:
            raise ValueError(f"Unsupported cache strategy: {self.config.strategy}")
        
        return strategy_class(
            max_size=self.config.max_size,
            max_memory_mb=self.config.max_memory_mb
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache"""
        if self._is_circuit_breaker_open():
            self.metrics.record_error("circuit_breaker_open")
            return None
        
        start_time = time.time()
        
        try:
            # Get serialized value from strategy
            serialized_value = self.strategy.get(key)
            
            if serialized_value is None:
                self.metrics.record_miss()
                return None
            
            # Deserialize value
            value = self.serializer.deserialize(serialized_value)
            
            # Record metrics
            operation_time = time.time() - start_time
            self.metrics.record_hit()
            self.metrics.record_access_time(operation_time)
            self._record_operation_time(operation_time)
            
            return value
            
        except Exception as e:
            self.metrics.record_error(f"get_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        if self._is_circuit_breaker_open():
            self.metrics.record_error("circuit_breaker_open")
            return False
        
        start_time = time.time()
        
        try:
            # Use configured TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            # Serialize value
            serialized_value = self.serializer.serialize(value)
            
            # Store in strategy
            success = self.strategy.set(key, serialized_value, ttl)
            
            if success:
                # Record metrics
                operation_time = time.time() - start_time
                self.metrics.record_set()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
                self._reset_circuit_breaker()
            else:
                self.metrics.record_error("set_failed")
            
            return success
            
        except Exception as e:
            self.metrics.record_error(f"set_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        if self._is_circuit_breaker_open():
            self.metrics.record_error("circuit_breaker_open")
            return False
        
        start_time = time.time()
        
        try:
            success = self.strategy.delete(key)
            
            if success:
                operation_time = time.time() - start_time
                self.metrics.record_delete()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
                self._reset_circuit_breaker()
            
            return success
            
        except Exception as e:
            self.metrics.record_error(f"delete_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache"""
        if self._is_circuit_breaker_open():
            return False
        
        try:
            return self.strategy.contains(key)
        except Exception as e:
            self.metrics.record_error(f"exists_error: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """Clear all entries from the cache"""
        if self._is_circuit_breaker_open():
            self.metrics.record_error("circuit_breaker_open")
            return False
        
        try:
            self.strategy.clear()
            self.metrics.record_clear()
            self._reset_circuit_breaker()
            return True
        except Exception as e:
            self.metrics.record_error(f"clear_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def size(self) -> int:
        """Get the current size of the cache"""
        try:
            return self.strategy.size()
        except Exception:
            return 0
    
    def memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        try:
            return self.strategy.memory_usage()
        except Exception:
            return 0
    
    def keys(self) -> List[str]:
        """Get all keys in the cache"""
        try:
            return self.strategy.keys()
        except Exception:
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            strategy_stats = self.strategy.get_stats()
            metrics_stats = self.metrics.get_stats()
            
            # Add backend-specific stats
            backend_stats = {
                'backend_type': 'memory',
                'strategy_type': self.config.strategy.value,
                'serialization_format': self.config.serialization_format.value,
                'compression_enabled': self.config.compression_enabled,
                'circuit_breaker_open': self._circuit_breaker_open,
                'circuit_breaker_failures': self._circuit_breaker_failures,
                'avg_operation_time': self._get_avg_operation_time(),
                'max_operation_time': max(self._operation_times) if self._operation_times else 0,
                'min_operation_time': min(self._operation_times) if self._operation_times else 0
            }
            
            return {
                **strategy_stats,
                **metrics_stats,
                **backend_stats
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    # Async methods
    async def get_async(self, key: str) -> Optional[Any]:
        """Async version of get"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.get, key)
    
    async def set_async(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Async version of set"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.set, key, value, ttl)
    
    async def delete_async(self, key: str) -> bool:
        """Async version of delete"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.delete, key)
    
    async def exists_async(self, key: str) -> bool:
        """Async version of exists"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.exists, key)
    
    # Batch operations
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once"""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, items: Dict[str, Any], ttl: Optional[float] = None) -> Dict[str, bool]:
        """Set multiple values at once"""
        result = {}
        for key, value in items.items():
            result[key] = self.set(key, value, ttl)
        return result
    
    def delete_many(self, keys: List[str]) -> Dict[str, bool]:
        """Delete multiple values at once"""
        result = {}
        for key in keys:
            result[key] = self.delete(key)
        return result
    
    async def get_many_async(self, keys: List[str]) -> Dict[str, Any]:
        """Async version of get_many"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.get_many, keys)
    
    async def set_many_async(self, items: Dict[str, Any], ttl: Optional[float] = None) -> Dict[str, bool]:
        """Async version of set_many"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.set_many, items, ttl)
    
    async def delete_many_async(self, keys: List[str]) -> Dict[str, bool]:
        """Async version of delete_many"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.delete_many, keys)
    
    # Cache warming
    def warm_cache(self, data_loader: Callable[[], Dict[str, Any]], 
                   ttl: Optional[float] = None) -> Dict[str, bool]:
        """Warm the cache with data from a loader function"""
        try:
            data = data_loader()
            return self.set_many(data, ttl)
        except Exception as e:
            self.metrics.record_error(f"warm_cache_error: {str(e)}")
            return {}
    
    async def warm_cache_async(self, data_loader: Callable[[], Dict[str, Any]], 
                              ttl: Optional[float] = None) -> Dict[str, bool]:
        """Async version of warm_cache"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._thread_pool, self.warm_cache, data_loader, ttl)
    
    # Background cleanup
    def start_background_cleanup(self):
        """Start background cleanup thread"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._stop_cleanup.clear()
            self._cleanup_thread = threading.Thread(
                target=self._background_cleanup_worker,
                daemon=True,
                name="cache-cleanup"
            )
            self._cleanup_thread.start()
    
    def stop_background_cleanup(self):
        """Stop background cleanup thread"""
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)
    
    def _background_cleanup_worker(self):
        """Background worker for cache cleanup"""
        while not self._stop_cleanup.wait(self._cleanup_interval):
            try:
                # Perform cleanup based on strategy
                if hasattr(self.strategy, '_cleanup_expired'):
                    expired_count = self.strategy._cleanup_expired()
                    if expired_count > 0:
                        self.metrics.record_eviction(expired_count)
                
                # Optimize strategy if supported
                if hasattr(self.strategy, 'optimize'):
                    self.strategy.optimize()
                
                # Clean up operation time history
                if len(self._operation_times) > self._max_operation_history:
                    self._operation_times = self._operation_times[-self._max_operation_history//2:]
                
            except Exception as e:
                self.metrics.record_error(f"background_cleanup_error: {str(e)}")
    
    # Circuit breaker methods
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if not self._circuit_breaker_open:
            return False
        
        # Check if we should try to close the circuit breaker
        if (time.time() - self._circuit_breaker_last_failure > 
            self.config.circuit_breaker_recovery_timeout):
            self._circuit_breaker_open = False
            self._circuit_breaker_failures = 0
            return False
        
        return True
    
    def _handle_circuit_breaker_failure(self):
        """Handle a failure for circuit breaker logic"""
        self._circuit_breaker_failures += 1
        self._circuit_breaker_last_failure = time.time()
        
        if (self._circuit_breaker_failures >= 
            self.config.circuit_breaker_failure_threshold):
            self._circuit_breaker_open = True
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker on successful operation"""
        if self._circuit_breaker_failures > 0:
            self._circuit_breaker_failures = max(0, self._circuit_breaker_failures - 1)
    
    # Performance tracking
    def _record_operation_time(self, operation_time: float):
        """Record operation time for performance analysis"""
        self._operation_times.append(operation_time)
        if len(self._operation_times) > self._max_operation_history:
            self._operation_times.pop(0)
    
    def _get_avg_operation_time(self) -> float:
        """Get average operation time"""
        if not self._operation_times:
            return 0.0
        return sum(self._operation_times) / len(self._operation_times)
    
    # Health check
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the cache backend"""
        try:
            # Test basic operations
            test_key = "__health_check__"
            test_value = "test"
            
            start_time = time.time()
            
            # Test set
            set_success = self.set(test_key, test_value, 1.0)
            
            # Test get
            get_value = self.get(test_key) if set_success else None
            get_success = get_value == test_value
            
            # Test delete
            delete_success = self.delete(test_key) if set_success else False
            
            operation_time = time.time() - start_time
            
            health_status = {
                'healthy': set_success and get_success and delete_success,
                'backend_type': 'memory',
                'strategy_type': self.config.strategy.value,
                'operations': {
                    'set': set_success,
                    'get': get_success,
                    'delete': delete_success
                },
                'performance': {
                    'health_check_time': operation_time,
                    'avg_operation_time': self._get_avg_operation_time(),
                    'circuit_breaker_open': self._circuit_breaker_open
                },
                'stats': {
                    'size': self.size(),
                    'memory_usage_bytes': self.memory_usage(),
                    'hit_rate': self.metrics.get_hit_rate()
                }
            }
            
            return health_status
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'backend_type': 'memory',
                'strategy_type': self.config.strategy.value
            }
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_background_cleanup()
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
    
    def __del__(self):
        """Destructor"""
        try:
            self.stop_background_cleanup()
            if hasattr(self, '_thread_pool') and self._thread_pool:
                self._thread_pool.shutdown(wait=False)
        except Exception:
            pass  # Ignore errors during cleanup