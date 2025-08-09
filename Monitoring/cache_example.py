"""Cache System Usage Examples

Demonstrates various ways to use the advanced caching system with different
strategies, backends, and monitoring integration.
"""

import time
import asyncio
import random
from typing import List, Dict, Any
from datetime import datetime, timedelta

# Import monitoring components
from Monitoring.metrics.collector import MetricsCollector
from Monitoring.metrics.performance import PerformanceTracker
from Monitoring.log_utils.structured_logger import StructuredLogger
from Monitoring.health.checker import HealthChecker

# Import cache components
from Monitoring.cache import (
    CacheManager, CacheConfig
)
from Monitoring.cache.config import CacheStrategy, CacheBackend
from Monitoring.cache.decorators import (
    cache, cache_async, memoize, timed_cache, conditional_cache,
    set_default_cache_manager, clear_all_caches, get_cache_info
)


def setup_monitoring():
    """Setup monitoring components for cache examples"""
    metrics_collector = MetricsCollector()
    performance_tracker = PerformanceTracker(metrics_collector)
    logger = StructuredLogger()
    health_checker = HealthChecker()
    
    return metrics_collector, performance_tracker, logger, health_checker


def example_basic_cache_usage():
    """Basic cache usage example"""
    print("\n=== Basic Cache Usage ===")
    
    # Setup monitoring
    metrics_collector, performance_tracker, logger, health_checker = setup_monitoring()
    
    # Create cache manager with LRU strategy
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=100,
        default_ttl=300  # 5 minutes
    )
    
    cache_manager = CacheManager(
        config=config,
        metrics_collector=metrics_collector,
        performance_tracker=performance_tracker,
        logger=logger
    )
    
    # Basic operations
    print("Setting cache values...")
    cache_manager.set("user:1", {"name": "Alice", "age": 30})
    cache_manager.set("user:2", {"name": "Bob", "age": 25})
    cache_manager.set("config:app", {"debug": True, "version": "1.0.0"})
    
    print("Getting cache values...")
    user1 = cache_manager.get("user:1")
    user2 = cache_manager.get("user:2")
    config = cache_manager.get("config:app")
    
    print(f"User 1: {user1}")
    print(f"User 2: {user2}")
    print(f"Config: {config}")
    
    # Check cache statistics
    stats = cache_manager.get_stats()
    print(f"\nCache Stats: {stats}")
    
    # Health check
    health = cache_manager.health_check()
    print(f"Cache Health: {health['healthy']}")
    
    cache_manager.close()


def example_decorator_usage():
    """Cache decorator usage examples"""
    print("\n=== Cache Decorator Usage ===")
    
    # Setup cache manager
    config = CacheConfig(
        strategy=CacheStrategy.TTL,
        backend=CacheBackend.MEMORY,
        max_size=50,
        default_ttl=60  # 1 minute
    )
    
    cache_manager = CacheManager(config=config)
    set_default_cache_manager(cache_manager)
    
    # Example 1: Basic caching
    @cache(ttl=30)
    def expensive_computation(n: int) -> int:
        """Simulate expensive computation"""
        print(f"Computing factorial of {n}...")
        time.sleep(0.1)  # Simulate work
        result = 1
        for i in range(1, n + 1):
            result *= i
        return result
    
    print("First call (cache miss):")
    start_time = time.time()
    result1 = expensive_computation(10)
    time1 = time.time() - start_time
    print(f"Result: {result1}, Time: {time1:.3f}s")
    
    print("\nSecond call (cache hit):")
    start_time = time.time()
    result2 = expensive_computation(10)
    time2 = time.time() - start_time
    print(f"Result: {result2}, Time: {time2:.3f}s")
    
    # Example 2: Conditional caching
    @conditional_cache(
        condition=lambda x: x > 5,  # Only cache if x > 5
        ttl=60
    )
    def conditional_function(x: int) -> str:
        print(f"Processing {x}...")
        return f"Processed: {x}"
    
    print("\nConditional caching:")
    print(conditional_function(3))  # Won't be cached
    print(conditional_function(3))  # Will execute again
    print(conditional_function(10))  # Will be cached
    print(conditional_function(10))  # Cache hit
    
    # Example 3: Memoization
    @memoize(maxsize=32)
    def fibonacci(n: int) -> int:
        if n < 2:
            return n
        return fibonacci(n - 1) + fibonacci(n - 2)
    
    print("\nMemoized Fibonacci:")
    start_time = time.time()
    fib_result = fibonacci(30)
    fib_time = time.time() - start_time
    print(f"fibonacci(30) = {fib_result}, Time: {fib_time:.3f}s")
    
    # Second call should be much faster
    start_time = time.time()
    fib_result2 = fibonacci(30)
    fib_time2 = time.time() - start_time
    print(f"fibonacci(30) = {fib_result2}, Time: {fib_time2:.3f}s")
    
    cache_manager.close()


async def example_async_cache():
    """Async cache usage example"""
    print("\n=== Async Cache Usage ===")
    
    # Setup cache manager
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=100
    )
    
    cache_manager = CacheManager(config=config)
    set_default_cache_manager(cache_manager)
    
    @cache_async(ttl=30)
    async def async_api_call(endpoint: str) -> Dict[str, Any]:
        """Simulate async API call"""
        print(f"Making API call to {endpoint}...")
        await asyncio.sleep(0.2)  # Simulate network delay
        return {
            "endpoint": endpoint,
            "data": f"Response from {endpoint}",
            "timestamp": datetime.now().isoformat()
        }
    
    @cache_async(ttl=60)
    async def fetch_user_data(user_id: int) -> Dict[str, Any]:
        """Simulate fetching user data"""
        print(f"Fetching user data for ID {user_id}...")
        await asyncio.sleep(0.1)
        return {
            "id": user_id,
            "name": f"User {user_id}",
            "email": f"user{user_id}@example.com",
            "created_at": datetime.now().isoformat()
        }
    
    # Test async caching
    print("First async call (cache miss):")
    start_time = time.time()
    result1 = await async_api_call("/api/users")
    time1 = time.time() - start_time
    print(f"Result: {result1['endpoint']}, Time: {time1:.3f}s")
    
    print("\nSecond async call (cache hit):")
    start_time = time.time()
    result2 = await async_api_call("/api/users")
    time2 = time.time() - start_time
    print(f"Result: {result2['endpoint']}, Time: {time2:.3f}s")
    
    # Batch async operations
    print("\nBatch async operations:")
    user_ids = [1, 2, 3, 4, 5]
    
    start_time = time.time()
    users = await asyncio.gather(*[fetch_user_data(uid) for uid in user_ids])
    batch_time = time.time() - start_time
    print(f"Fetched {len(users)} users in {batch_time:.3f}s")
    
    # Second batch should be faster (cache hits)
    start_time = time.time()
    users2 = await asyncio.gather(*[fetch_user_data(uid) for uid in user_ids])
    batch_time2 = time.time() - start_time
    print(f"Fetched {len(users2)} users in {batch_time2:.3f}s (cached)")
    
    cache_manager.close()


def example_different_strategies():
    """Demonstrate different cache strategies"""
    print("\n=== Different Cache Strategies ===")
    
    strategies = [
        (CacheStrategy.LRU, "Least Recently Used"),
        (CacheStrategy.TTL, "Time To Live"),
        (CacheStrategy.FIFO, "First In, First Out"),
        (CacheStrategy.LFU, "Least Frequently Used")
    ]
    
    for strategy, description in strategies:
        print(f"\n--- {description} ({strategy.value}) ---")
        
        config = CacheConfig(
            strategy=strategy,
            backend=CacheBackend.MEMORY,
            max_size=5,  # Small size to trigger eviction
            default_ttl=10 if strategy == CacheStrategy.TTL else None
        )
        
        cache_manager = CacheManager(config=config)
        
        # Fill cache beyond capacity
        for i in range(8):
            key = f"item_{i}"
            value = f"value_{i}"
            cache_manager.set(key, value)
            print(f"Set {key} = {value}")
            
            # Show current cache state
            current_keys = cache_manager.get_keys()
            print(f"  Current keys: {current_keys}")
            
            if strategy == CacheStrategy.TTL:
                time.sleep(0.1)  # Small delay for TTL demonstration
        
        # Final statistics
        stats = cache_manager.get_stats()
        print(f"Final stats: Size={cache_manager.get_size()}, Keys={cache_manager.get_keys()}")
        
        cache_manager.close()


def example_batch_operations():
    """Demonstrate batch cache operations"""
    print("\n=== Batch Operations ===")
    
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=100
    )
    
    cache_manager = CacheManager(config=config)
    
    # Batch set
    print("Batch setting values...")
    batch_data = {
        f"product_{i}": {
            "id": i,
            "name": f"Product {i}",
            "price": random.uniform(10, 100)
        }
        for i in range(1, 11)
    }
    
    set_results = cache_manager.set_many(batch_data, ttl=60)
    successful_sets = sum(1 for success in set_results.values() if success)
    print(f"Successfully set {successful_sets}/{len(batch_data)} items")
    
    # Batch get
    print("\nBatch getting values...")
    keys_to_get = [f"product_{i}" for i in range(1, 11)]
    batch_results = cache_manager.get_many(keys_to_get)
    print(f"Retrieved {len(batch_results)} items")
    
    for key, value in batch_results.items():
        print(f"  {key}: {value['name']} - ${value['price']:.2f}")
    
    # Batch delete
    print("\nBatch deleting some values...")
    keys_to_delete = [f"product_{i}" for i in range(1, 6)]
    delete_results = cache_manager.delete_many(keys_to_delete)
    successful_deletes = sum(1 for success in delete_results.values() if success)
    print(f"Successfully deleted {successful_deletes}/{len(keys_to_delete)} items")
    
    # Check remaining items
    remaining_keys = cache_manager.get_keys()
    print(f"Remaining keys: {remaining_keys}")
    
    cache_manager.close()


def example_cache_warming():
    """Demonstrate cache warming"""
    print("\n=== Cache Warming ===")
    
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=100
    )
    
    cache_manager = CacheManager(config=config)
    
    def load_initial_data() -> Dict[str, Any]:
        """Simulate loading data from database"""
        print("Loading initial data from database...")
        time.sleep(0.5)  # Simulate database query time
        
        return {
            "config:database_url": "postgresql://localhost:5432/mydb",
            "config:redis_url": "redis://localhost:6379",
            "config:api_key": "secret-api-key-12345",
            "config:max_connections": 100,
            "config:timeout": 30,
            "feature_flags:new_ui": True,
            "feature_flags:beta_features": False,
            "feature_flags:analytics": True
        }
    
    # Warm the cache
    print("Warming cache...")
    start_time = time.time()
    warm_results = cache_manager.warm_cache(load_initial_data, ttl=300)
    warm_time = time.time() - start_time
    
    successful_loads = sum(1 for success in warm_results.values() if success)
    print(f"Cache warming completed in {warm_time:.3f}s")
    print(f"Successfully loaded {successful_loads}/{len(warm_results)} items")
    
    # Test cache hits
    print("\nTesting cache hits after warming:")
    test_keys = ["config:database_url", "feature_flags:new_ui", "config:timeout"]
    
    for key in test_keys:
        start_time = time.time()
        value = cache_manager.get(key)
        get_time = time.time() - start_time
        print(f"  {key}: {value} (retrieved in {get_time:.6f}s)")
    
    cache_manager.close()


def example_monitoring_integration():
    """Demonstrate monitoring integration"""
    print("\n=== Monitoring Integration ===")
    
    # Setup comprehensive monitoring
    metrics_collector = MetricsCollector()
    performance_tracker = PerformanceTracker(metrics_collector)
    logger = StructuredLogger()
    health_checker = HealthChecker()
    
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=50,
        enable_metrics=True,
        enable_detailed_logging=True
    )
    
    cache_manager = CacheManager(
        config=config,
        metrics_collector=metrics_collector,
        performance_tracker=performance_tracker,
        logger=logger
    )
    
    # Perform various operations to generate metrics
    print("Performing operations to generate metrics...")
    
    # Mix of hits and misses
    for i in range(20):
        key = f"test_key_{i % 10}"  # This will create some cache hits
        value = f"test_value_{i}"
        
        # Set operation
        cache_manager.set(key, value)
        
        # Get operation (some will be hits, some misses)
        retrieved = cache_manager.get(key)
        
        # Some random gets that will be misses
        cache_manager.get(f"nonexistent_key_{i}")
    
    # Get comprehensive statistics
    stats = cache_manager.get_stats()
    print("\nCache Statistics:")
    print(f"  Total Operations: {stats.get('manager', {}).get('operations', {}).get('total_operations', 0)}")
    print(f"  Successful Operations: {stats.get('manager', {}).get('operations', {}).get('successful_operations', 0)}")
    print(f"  Average Response Time: {stats.get('manager', {}).get('operations', {}).get('avg_response_time', 0):.6f}s")
    
    # Health check
    health = cache_manager.health_check()
    print(f"\nHealth Status: {'✓ Healthy' if health['healthy'] else '✗ Unhealthy'}")
    print(f"Success Rate: {health.get('manager', {}).get('success_rate', 0):.2%}")
    
    # Cache metrics
    hit_rate = cache_manager.get_hit_rate()
    print(f"Hit Rate: {hit_rate:.2%}")
    print(f"Cache Size: {cache_manager.get_size()} items")
    print(f"Memory Usage: {cache_manager.get_memory_usage()} bytes")
    
    cache_manager.close()


def example_error_handling():
    """Demonstrate error handling and resilience"""
    print("\n=== Error Handling ===")
    
    config = CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=10
    )
    
    cache_manager = CacheManager(config=config)
    
    # Test with problematic data
    print("Testing with various data types...")
    
    test_data = [
        ("string", "Hello, World!"),
        ("integer", 42),
        ("float", 3.14159),
        ("list", [1, 2, 3, 4, 5]),
        ("dict", {"key": "value", "nested": {"inner": "data"}}),
        ("none", None),
        ("boolean", True)
    ]
    
    for key, value in test_data:
        try:
            success = cache_manager.set(key, value)
            retrieved = cache_manager.get(key)
            print(f"  {key}: Set={success}, Retrieved={retrieved == value}")
        except Exception as e:
            print(f"  {key}: Error - {e}")
    
    # Test cache behavior when closed
    print("\nTesting operations after cache is closed...")
    cache_manager.close()
    
    try:
        cache_manager.set("after_close", "value")
        print("  Set after close: Unexpected success")
    except RuntimeError as e:
        print(f"  Set after close: Expected error - {e}")
    
    try:
        value = cache_manager.get("test_key")
        print(f"  Get after close: Unexpected success - {value}")
    except RuntimeError as e:
        print(f"  Get after close: Expected error - {e}")


def main():
    """Run all cache examples"""
    print("Advanced Caching System Examples")
    print("=" * 50)
    
    try:
        # Run synchronous examples
        example_basic_cache_usage()
        example_decorator_usage()
        example_different_strategies()
        example_batch_operations()
        example_cache_warming()
        example_monitoring_integration()
        example_error_handling()
        
        # Run async example
        print("\nRunning async examples...")
        asyncio.run(example_async_cache())
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
        # Final cache info
        cache_info = get_cache_info()
        if cache_info:
            print(f"\nFinal cache information: {cache_info}")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            clear_all_caches()
            print("\nCache cleanup completed.")
        except Exception:
            pass


if __name__ == "__main__":
    main()