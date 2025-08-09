"""Comprehensive tests for the advanced caching system

Tests all cache strategies, backends, decorators, and integration with monitoring.
"""

import pytest
import time
import asyncio
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Import cache components
from Monitoring.cache import (
    CacheManager, CacheConfig, CacheStrategy, CacheBackend,
    cache, cache_async, memoize, timed_cache,
    set_default_cache_manager, clear_all_caches
)
from Monitoring.cache.strategies import LRUStrategy, TTLStrategy, FIFOStrategy, LFUStrategy
from Monitoring.cache.backends import MemoryBackend
from Monitoring.cache.metrics import CacheMetrics, CacheStats
from Monitoring.cache.serializers import JSONSerializer, PickleSerializer

# Import monitoring components
from Monitoring.metrics import MetricsCollector
from Monitoring.performance import PerformanceTracker
from Monitoring.log_utils import StructuredLogger


class TestCacheConfig:
    """Test cache configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = CacheConfig()
        
        assert config.strategy == CacheStrategy.LRU
        assert config.backend == CacheBackend.MEMORY
        assert config.max_size == 1000
        assert config.default_ttl is None
        assert config.enable_metrics is True
        assert config.enable_detailed_logging is False
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = CacheConfig(
            strategy=CacheStrategy.TTL,
            backend=CacheBackend.REDIS,
            max_size=500,
            default_ttl=300,
            enable_metrics=False
        )
        
        assert config.strategy == CacheStrategy.TTL
        assert config.backend == CacheBackend.REDIS
        assert config.max_size == 500
        assert config.default_ttl == 300
        assert config.enable_metrics is False
    
    def test_from_dict(self):
        """Test configuration from dictionary"""
        config_dict = {
            'strategy': 'lru',
            'backend': 'memory',
            'max_size': 200,
            'default_ttl': 600
        }
        
        config = CacheConfig.from_dict(config_dict)
        
        assert config.strategy == CacheStrategy.LRU
        assert config.backend == CacheBackend.MEMORY
        assert config.max_size == 200
        assert config.default_ttl == 600


class TestCacheStrategies:
    """Test different cache strategies"""
    
    def test_lru_strategy(self):
        """Test LRU (Least Recently Used) strategy"""
        strategy = LRUStrategy(max_size=3)
        
        # Fill cache
        strategy.set("a", "value_a")
        strategy.set("b", "value_b")
        strategy.set("c", "value_c")
        
        assert strategy.size() == 3
        assert strategy.get("a") == "value_a"
        assert strategy.get("b") == "value_b"
        assert strategy.get("c") == "value_c"
        
        # Access 'a' to make it recently used
        strategy.get("a")
        
        # Add new item, should evict 'b' (least recently used)
        strategy.set("d", "value_d")
        
        assert strategy.size() == 3
        assert strategy.get("a") == "value_a"  # Still there
        assert strategy.get("b") is None  # Evicted
        assert strategy.get("c") == "value_c"  # Still there
        assert strategy.get("d") == "value_d"  # New item
    
    def test_ttl_strategy(self):
        """Test TTL (Time To Live) strategy"""
        strategy = TTLStrategy(max_size=10)
        
        # Set items with different TTLs
        strategy.set("short", "value1", ttl=0.1)  # 100ms
        strategy.set("long", "value2", ttl=10.0)   # 10s
        strategy.set("no_ttl", "value3")          # No TTL
        
        assert strategy.get("short") == "value1"
        assert strategy.get("long") == "value2"
        assert strategy.get("no_ttl") == "value3"
        
        # Wait for short TTL to expire
        time.sleep(0.15)
        
        assert strategy.get("short") is None  # Expired
        assert strategy.get("long") == "value2"  # Still valid
        assert strategy.get("no_ttl") == "value3"  # No expiration
    
    def test_fifo_strategy(self):
        """Test FIFO (First In, First Out) strategy"""
        strategy = FIFOStrategy(max_size=3)
        
        # Fill cache in order
        strategy.set("first", "value1")
        strategy.set("second", "value2")
        strategy.set("third", "value3")
        
        assert strategy.size() == 3
        
        # Add fourth item, should evict first
        strategy.set("fourth", "value4")
        
        assert strategy.size() == 3
        assert strategy.get("first") is None  # Evicted (first in)
        assert strategy.get("second") == "value2"
        assert strategy.get("third") == "value3"
        assert strategy.get("fourth") == "value4"
    
    def test_lfu_strategy(self):
        """Test LFU (Least Frequently Used) strategy"""
        strategy = LFUStrategy(max_size=3)
        
        # Fill cache
        strategy.set("a", "value_a")
        strategy.set("b", "value_b")
        strategy.set("c", "value_c")
        
        # Access 'a' multiple times to increase frequency
        for _ in range(5):
            strategy.get("a")
        
        # Access 'b' a few times
        for _ in range(2):
            strategy.get("b")
        
        # 'c' is accessed only once (least frequent)
        strategy.get("c")
        
        # Add new item, should evict 'c' (least frequently used)
        strategy.set("d", "value_d")
        
        assert strategy.size() == 3
        assert strategy.get("a") == "value_a"  # Most frequent
        assert strategy.get("b") == "value_b"  # Medium frequent
        assert strategy.get("c") is None  # Evicted (least frequent)
        assert strategy.get("d") == "value_d"  # New item


class TestMemoryBackend:
    """Test memory backend functionality"""
    
    def test_basic_operations(self):
        """Test basic cache operations"""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_size=10)
        backend = MemoryBackend(config)
        
        # Test set and get
        assert backend.set("key1", "value1") is True
        assert backend.get("key1") == "value1"
        
        # Test non-existent key
        assert backend.get("nonexistent") is None
        
        # Test exists
        assert backend.exists("key1") is True
        assert backend.exists("nonexistent") is False
        
        # Test delete
        assert backend.delete("key1") is True
        assert backend.get("key1") is None
        assert backend.delete("nonexistent") is False
    
    def test_batch_operations(self):
        """Test batch operations"""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_size=10)
        backend = MemoryBackend(config)
        
        # Batch set
        items = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        }
        
        results = backend.set_many(items)
        assert all(results.values())
        
        # Batch get
        keys = ["key1", "key2", "key3", "nonexistent"]
        batch_results = backend.get_many(keys)
        
        assert batch_results["key1"] == "value1"
        assert batch_results["key2"] == "value2"
        assert batch_results["key3"] == "value3"
        assert "nonexistent" not in batch_results
        
        # Batch delete
        delete_keys = ["key1", "key3"]
        delete_results = backend.delete_many(delete_keys)
        
        assert delete_results["key1"] is True
        assert delete_results["key3"] is True
        
        # Verify deletions
        assert backend.get("key1") is None
        assert backend.get("key2") == "value2"  # Still exists
        assert backend.get("key3") is None
    
    def test_cache_warming(self):
        """Test cache warming functionality"""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_size=10)
        backend = MemoryBackend(config)
        
        def data_loader():
            return {
                "config1": "value1",
                "config2": "value2",
                "config3": "value3"
            }
        
        results = backend.warm_cache(data_loader)
        
        assert all(results.values())
        assert backend.get("config1") == "value1"
        assert backend.get("config2") == "value2"
        assert backend.get("config3") == "value3"
    
    def test_health_check(self):
        """Test health check functionality"""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_size=10)
        backend = MemoryBackend(config)
        
        health = backend.health_check()
        
        assert health["healthy"] is True
        assert "strategy" in health
        assert "size" in health
        assert "memory_usage" in health


class TestCacheManager:
    """Test cache manager functionality"""
    
    def test_initialization(self):
        """Test cache manager initialization"""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_size=100)
        cache_manager = CacheManager(config=config)
        
        assert cache_manager.config == config
        assert cache_manager._initialized is True
        assert cache_manager._closed is False
        
        cache_manager.close()
    
    def test_basic_operations(self):
        """Test basic cache manager operations"""
        cache_manager = CacheManager()
        
        # Test set and get
        assert cache_manager.set("test_key", "test_value") is True
        assert cache_manager.get("test_key") == "test_value"
        
        # Test default value
        assert cache_manager.get("nonexistent", "default") == "default"
        
        # Test exists
        assert cache_manager.exists("test_key") is True
        assert cache_manager.exists("nonexistent") is False
        
        # Test delete
        assert cache_manager.delete("test_key") is True
        assert cache_manager.get("test_key") is None
        
        cache_manager.close()
    
    @pytest.mark.asyncio
    async def test_async_operations(self):
        """Test async cache operations"""
        cache_manager = CacheManager()
        
        # Test async set and get
        assert await cache_manager.set_async("async_key", "async_value") is True
        assert await cache_manager.get_async("async_key") == "async_value"
        
        # Test async delete
        assert await cache_manager.delete_async("async_key") is True
        assert await cache_manager.get_async("async_key") is None
        
        cache_manager.close()
    
    def test_batch_operations(self):
        """Test batch operations through cache manager"""
        cache_manager = CacheManager()
        
        # Batch set
        items = {
            "batch1": "value1",
            "batch2": "value2",
            "batch3": "value3"
        }
        
        results = cache_manager.set_many(items)
        assert all(results.values())
        
        # Batch get
        keys = ["batch1", "batch2", "batch3"]
        batch_results = cache_manager.get_many(keys)
        
        assert len(batch_results) == 3
        assert batch_results["batch1"] == "value1"
        
        cache_manager.close()
    
    def test_get_or_set(self):
        """Test get_or_set convenience method"""
        cache_manager = CacheManager()
        
        def value_factory():
            return "computed_value"
        
        # First call should compute and cache
        result1 = cache_manager.get_or_set("computed_key", value_factory)
        assert result1 == "computed_value"
        
        # Second call should return cached value
        result2 = cache_manager.get_or_set("computed_key", lambda: "different_value")
        assert result2 == "computed_value"  # Should be cached value
        
        cache_manager.close()
    
    def test_increment_decrement(self):
        """Test increment and decrement operations"""
        cache_manager = CacheManager()
        
        # Test increment with default
        result = cache_manager.increment("counter", default=0)
        assert result == 1
        
        # Test increment existing value
        result = cache_manager.increment("counter", amount=5)
        assert result == 6
        
        # Test decrement
        result = cache_manager.decrement("counter", amount=2)
        assert result == 4
        
        cache_manager.close()
    
    def test_statistics(self):
        """Test statistics collection"""
        cache_manager = CacheManager()
        
        # Perform some operations
        cache_manager.set("key1", "value1")
        cache_manager.get("key1")
        cache_manager.get("nonexistent")
        
        stats = cache_manager.get_stats()
        
        assert "manager" in stats
        assert "operations" in stats["manager"]
        assert stats["manager"]["operations"]["total_operations"] > 0
        
        cache_manager.close()
    
    def test_health_check(self):
        """Test health check"""
        cache_manager = CacheManager()
        
        health = cache_manager.health_check()
        
        assert health["healthy"] is True
        assert "backend" in health
        assert "manager" in health
        assert "timestamp" in health
        
        cache_manager.close()
    
    def test_context_manager(self):
        """Test context manager functionality"""
        config = CacheConfig(max_size=10)
        
        with CacheManager(config=config) as cache_manager:
            cache_manager.set("context_key", "context_value")
            assert cache_manager.get("context_key") == "context_value"
        
        # Cache should be closed after context
        assert cache_manager._closed is True
    
    def test_closed_cache_operations(self):
        """Test operations on closed cache"""
        cache_manager = CacheManager()
        cache_manager.close()
        
        with pytest.raises(RuntimeError, match="Cache manager has been closed"):
            cache_manager.set("key", "value")
        
        with pytest.raises(RuntimeError, match="Cache manager has been closed"):
            cache_manager.get("key")


class TestCacheDecorators:
    """Test cache decorators"""
    
    def test_basic_cache_decorator(self):
        """Test basic cache decorator"""
        call_count = 0
        
        @cache(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call (should be cached)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented
        
        # Different argument (cache miss)
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2
    
    def test_memoize_decorator(self):
        """Test memoize decorator"""
        call_count = 0
        
        @memoize(maxsize=32)
        def fibonacci(n):
            nonlocal call_count
            call_count += 1
            if n < 2:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)
        
        result = fibonacci(10)
        assert result == 55
        # Should be much fewer calls due to memoization
        assert call_count < 20  # Without memoization, it would be much higher
    
    def test_timed_cache_decorator(self):
        """Test timed cache decorator"""
        call_count = 0
        
        @timed_cache(seconds=0.1)  # 100ms TTL
        def timed_function(x):
            nonlocal call_count
            call_count += 1
            return x * 3
        
        # First call
        result1 = timed_function(5)
        assert result1 == 15
        assert call_count == 1
        
        # Second call within TTL (cached)
        result2 = timed_function(5)
        assert result2 == 15
        assert call_count == 1
        
        # Wait for TTL to expire
        time.sleep(0.15)
        
        # Third call after TTL (cache miss)
        result3 = timed_function(5)
        assert result3 == 15
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_cache_decorator(self):
        """Test async cache decorator"""
        call_count = 0
        
        @cache_async(ttl=60)
        async def async_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate async work
            return x * 4
        
        # First call
        result1 = await async_function(5)
        assert result1 == 20
        assert call_count == 1
        
        # Second call (should be cached)
        result2 = await async_function(5)
        assert result2 == 20
        assert call_count == 1
    
    def test_cache_invalidation(self):
        """Test cache invalidation methods"""
        call_count = 0
        
        @cache(ttl=300)
        def cached_function(x):
            nonlocal call_count
            call_count += 1
            return x * 5
        
        # Cache a value
        result1 = cached_function(10)
        assert result1 == 50
        assert call_count == 1
        
        # Invalidate specific cache entry
        cached_function.invalidate(10)
        
        # Should recompute after invalidation
        result2 = cached_function(10)
        assert result2 == 50
        assert call_count == 2
    
    def test_conditional_caching(self):
        """Test conditional caching"""
        call_count = 0
        
        @cache(condition=lambda x: x > 5)  # Only cache if x > 5
        def conditional_function(x):
            nonlocal call_count
            call_count += 1
            return x * 6
        
        # Call with x <= 5 (should not cache)
        result1 = conditional_function(3)
        assert result1 == 18
        assert call_count == 1
        
        result2 = conditional_function(3)  # Should call again
        assert result2 == 18
        assert call_count == 2
        
        # Call with x > 5 (should cache)
        result3 = conditional_function(10)
        assert result3 == 60
        assert call_count == 3
        
        result4 = conditional_function(10)  # Should use cache
        assert result4 == 60
        assert call_count == 3  # Not incremented


class TestCacheMetrics:
    """Test cache metrics functionality"""
    
    def test_cache_stats(self):
        """Test cache statistics tracking"""
        stats = CacheStats()
        
        # Test initial state
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 0.0
        
        # Record some operations
        stats.hits = 7
        stats.misses = 3
        
        assert stats.hit_rate == 0.7
        assert stats.miss_rate == 0.3
    
    def test_cache_metrics_integration(self):
        """Test cache metrics integration with monitoring"""
        metrics_collector = Mock(spec=MetricsCollector)
        logger = Mock(spec=StructuredLogger)
        
        cache_metrics = CacheMetrics(
            metrics_collector=metrics_collector,
            logger=logger
        )
        
        # Record operations
        cache_metrics.record_hit("test_key")
        cache_metrics.record_miss("missing_key")
        cache_metrics.record_set("new_key", 100)
        
        # Verify metrics were recorded
        assert metrics_collector.increment.called
        assert logger.debug.called


class TestCacheSerializers:
    """Test cache serializers"""
    
    def test_json_serializer(self):
        """Test JSON serializer"""
        serializer = JSONSerializer()
        
        # Test basic data types
        test_data = {
            "string": "hello",
            "number": 42,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        }
        
        serialized = serializer.serialize(test_data)
        deserialized = serializer.deserialize(serialized)
        
        assert deserialized == test_data
    
    def test_pickle_serializer(self):
        """Test Pickle serializer"""
        serializer = PickleSerializer()
        
        # Test complex objects
        class TestClass:
            def __init__(self, value):
                self.value = value
            
            def __eq__(self, other):
                return isinstance(other, TestClass) and self.value == other.value
        
        test_obj = TestClass("test_value")
        
        serialized = serializer.serialize(test_obj)
        deserialized = serializer.deserialize(serialized)
        
        assert deserialized == test_obj
        assert deserialized.value == "test_value"


class TestCacheIntegration:
    """Integration tests for the complete cache system"""
    
    def test_full_system_integration(self):
        """Test complete system integration"""
        # Setup monitoring components
        metrics_collector = MetricsCollector()
        performance_tracker = PerformanceTracker(metrics_collector)
        logger = StructuredLogger()
        
        # Create cache manager with monitoring
        config = CacheConfig(
            strategy=CacheStrategy.LRU,
            backend=CacheBackend.MEMORY,
            max_size=100,
            enable_metrics=True
        )
        
        cache_manager = CacheManager(
            config=config,
            metrics_collector=metrics_collector,
            performance_tracker=performance_tracker,
            logger=logger
        )
        
        # Set default cache manager for decorators
        set_default_cache_manager(cache_manager)
        
        # Test decorated function
        @cache(ttl=60)
        def integrated_function(x, y):
            return x + y
        
        # Perform operations
        result1 = integrated_function(5, 10)
        assert result1 == 15
        
        result2 = integrated_function(5, 10)  # Should be cached
        assert result2 == 15
        
        # Check statistics
        stats = cache_manager.get_stats()
        assert stats["manager"]["operations"]["total_operations"] > 0
        
        # Health check
        health = cache_manager.health_check()
        assert health["healthy"] is True
        
        cache_manager.close()
    
    def test_concurrent_access(self):
        """Test concurrent cache access"""
        cache_manager = CacheManager()
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for i in range(10):
                    key = f"worker_{worker_id}_item_{i}"
                    value = f"value_{worker_id}_{i}"
                    
                    # Set value
                    cache_manager.set(key, value)
                    
                    # Get value
                    retrieved = cache_manager.get(key)
                    results.append((key, retrieved == value))
                    
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 50  # 5 workers * 10 items each
        assert all(success for _, success in results)
        
        cache_manager.close()
    
    def test_error_recovery(self):
        """Test error recovery and resilience"""
        cache_manager = CacheManager()
        
        # Test with various problematic inputs
        test_cases = [
            ("normal_key", "normal_value"),
            ("unicode_key_🔑", "unicode_value_🎯"),
            ("empty_value", ""),
            ("none_value", None),
            ("large_key", "x" * 1000),
            ("complex_value", {"nested": {"deep": [1, 2, 3]}})
        ]
        
        for key, value in test_cases:
            try:
                # Should handle all cases gracefully
                success = cache_manager.set(key, value)
                if success:
                    retrieved = cache_manager.get(key)
                    # For None values, we expect None back
                    if value is None:
                        assert retrieved is None
                    else:
                        assert retrieved == value
            except Exception as e:
                pytest.fail(f"Unexpected error for {key}: {e}")
        
        cache_manager.close()
    
    @pytest.mark.asyncio
    async def test_async_integration(self):
        """Test async integration"""
        cache_manager = CacheManager()
        set_default_cache_manager(cache_manager)
        
        @cache_async(ttl=60)
        async def async_computation(x, y):
            await asyncio.sleep(0.01)  # Simulate async work
            return x * y
        
        # Test concurrent async calls
        tasks = [
            async_computation(i, i + 1)
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify results
        expected = [i * (i + 1) for i in range(10)]
        assert results == expected
        
        # Test that cached values are returned quickly
        start_time = time.time()
        cached_result = await async_computation(5, 6)
        elapsed = time.time() - start_time
        
        assert cached_result == 30
        assert elapsed < 0.005  # Should be much faster than 0.01s
        
        cache_manager.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])