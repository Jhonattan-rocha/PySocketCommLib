"""Redis Backend for Cache System

Provides Redis-based distributed caching with comprehensive monitoring and resilience features.
"""

import time
import json
import asyncio
from typing import Any, Optional, Dict, List, Union, Callable
from concurrent.futures import ThreadPoolExecutor

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    aioredis = None
    REDIS_AVAILABLE = False

from ..config import CacheConfig, RedisConfig
from ..metrics import CacheMetrics
from ..serializers import SerializerFactory
from ...log_utils.structured_logger import StructuredLogger


class RedisBackend:
    """Redis-based cache backend with comprehensive features"""
    
    def __init__(self, config: CacheConfig, metrics: Optional[CacheMetrics] = None):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Install with: pip install redis")
        
        self.config = config
        self.redis_config = config.redis_config
        self.metrics = metrics or CacheMetrics()
        
        # Initialize serializer
        self.serializer = SerializerFactory.create_serializer(
            config.serialization_format,
            enable_compression=config.enable_compression,
            compression_threshold=config.compression_threshold
        )
        
        # Initialize Redis connections
        self._redis_client = None
        self._async_redis_client = None
        self._connection_pool = None
        self._async_connection_pool = None
        
        # Thread pool for async operations
        self._thread_pool = ThreadPoolExecutor(
            max_workers=config.max_concurrent_operations,
            thread_name_prefix="redis-cache-worker"
        )
        
        # Circuit breaker state
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = 0
        self._circuit_breaker_open = False
        
        # Performance tracking
        self._operation_times = []
        self._max_operation_history = 1000
        
        # Connection state
        self._connected = False
        self._last_connection_attempt = 0
        self._connection_retry_delay = 5.0
        
        # Initialize connections
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize Redis connections"""
        try:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool(
                host=self.redis_config.host,
                port=self.redis_config.port,
                db=self.redis_config.db,
                password=self.redis_config.password,
                socket_timeout=self.redis_config.socket_timeout,
                socket_connect_timeout=self.redis_config.socket_connect_timeout,
                max_connections=self.redis_config.max_connections,
                retry_on_timeout=True,
                decode_responses=False  # We handle serialization ourselves
            )
            
            # Create sync client
            self._redis_client = redis.Redis(
                connection_pool=self._connection_pool,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            
            # Test connection
            self._redis_client.ping()
            self._connected = True
            self._reset_circuit_breaker()
            
        except Exception as e:
            self.metrics.record_error(f"redis_connection_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            self._connected = False
    
    async def _initialize_async_connection(self):
        """Initialize async Redis connection"""
        if self._async_redis_client is None:
            try:
                self._async_redis_client = aioredis.Redis(
                    host=self.redis_config.host,
                    port=self.redis_config.port,
                    db=self.redis_config.db,
                    password=self.redis_config.password,
                    socket_timeout=self.redis_config.socket_timeout,
                    socket_connect_timeout=self.redis_config.socket_connect_timeout,
                    max_connections=self.redis_config.max_connections,
                    decode_responses=False
                )
                
                # Test connection
                await self._async_redis_client.ping()
                
            except Exception as e:
                self.metrics.record_error(f"async_redis_connection_error: {str(e)}")
                self._async_redis_client = None
                raise
    
    def _ensure_connection(self) -> bool:
        """Ensure Redis connection is available"""
        if self._is_circuit_breaker_open():
            return False
        
        if not self._connected:
            current_time = time.time()
            if current_time - self._last_connection_attempt > self._connection_retry_delay:
                self._last_connection_attempt = current_time
                self._initialize_connections()
        
        return self._connected
    
    def _get_key(self, key: str) -> str:
        """Get prefixed key for Redis"""
        if self.redis_config.key_prefix:
            return f"{self.redis_config.key_prefix}:{key}"
        return key
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis cache"""
        if not self._ensure_connection():
            self.metrics.record_error("redis_not_connected")
            return None
        
        start_time = time.time()
        redis_key = self._get_key(key)
        
        try:
            # Get serialized value from Redis
            serialized_value = self._redis_client.get(redis_key)
            
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
            self._reset_circuit_breaker()
            
            return value
            
        except Exception as e:
            self.metrics.record_error(f"redis_get_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in Redis cache"""
        if not self._ensure_connection():
            self.metrics.record_error("redis_not_connected")
            return False
        
        start_time = time.time()
        redis_key = self._get_key(key)
        
        try:
            # Use configured TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            # Serialize value
            serialized_value = self.serializer.serialize(value)
            
            # Store in Redis with TTL
            if ttl and ttl > 0:
                success = self._redis_client.setex(redis_key, int(ttl), serialized_value)
            else:
                success = self._redis_client.set(redis_key, serialized_value)
            
            if success:
                # Record metrics
                operation_time = time.time() - start_time
                self.metrics.record_set()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
                self._reset_circuit_breaker()
            else:
                self.metrics.record_error("redis_set_failed")
            
            return bool(success)
            
        except Exception as e:
            self.metrics.record_error(f"redis_set_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from Redis cache"""
        if not self._ensure_connection():
            self.metrics.record_error("redis_not_connected")
            return False
        
        start_time = time.time()
        redis_key = self._get_key(key)
        
        try:
            deleted_count = self._redis_client.delete(redis_key)
            success = deleted_count > 0
            
            if success:
                operation_time = time.time() - start_time
                self.metrics.record_delete()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
                self._reset_circuit_breaker()
            
            return success
            
        except Exception as e:
            self.metrics.record_error(f"redis_delete_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis cache"""
        if not self._ensure_connection():
            return False
        
        redis_key = self._get_key(key)
        
        try:
            return bool(self._redis_client.exists(redis_key))
        except Exception as e:
            self.metrics.record_error(f"redis_exists_error: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """Clear all entries from Redis cache (with prefix)"""
        if not self._ensure_connection():
            self.metrics.record_error("redis_not_connected")
            return False
        
        try:
            if self.redis_config.key_prefix:
                # Delete keys with prefix
                pattern = f"{self.redis_config.key_prefix}:*"
                keys = self._redis_client.keys(pattern)
                if keys:
                    self._redis_client.delete(*keys)
            else:
                # Clear entire database (use with caution!)
                self._redis_client.flushdb()
            
            self.metrics.record_clear()
            self._reset_circuit_breaker()
            return True
            
        except Exception as e:
            self.metrics.record_error(f"redis_clear_error: {str(e)}")
            self._handle_circuit_breaker_failure()
            return False
    
    def size(self) -> int:
        """Get the current size of the cache"""
        if not self._ensure_connection():
            return 0
        
        try:
            if self.redis_config.key_prefix:
                pattern = f"{self.redis_config.key_prefix}:*"
                keys = self._redis_client.keys(pattern)
                return len(keys)
            else:
                return self._redis_client.dbsize()
        except Exception:
            return 0
    
    def memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        if not self._ensure_connection():
            return 0
        
        try:
            info = self._redis_client.info('memory')
            return info.get('used_memory', 0)
        except Exception:
            return 0
    
    def keys(self) -> List[str]:
        """Get all keys in the cache"""
        if not self._ensure_connection():
            return []
        
        try:
            if self.redis_config.key_prefix:
                pattern = f"{self.redis_config.key_prefix}:*"
                redis_keys = self._redis_client.keys(pattern)
                # Remove prefix from keys
                prefix_len = len(self.redis_config.key_prefix) + 1
                return [key.decode('utf-8')[prefix_len:] for key in redis_keys]
            else:
                redis_keys = self._redis_client.keys('*')
                return [key.decode('utf-8') for key in redis_keys]
        except Exception:
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            metrics_stats = self.metrics.get_stats()
            
            # Get Redis info
            redis_info = {}
            if self._ensure_connection():
                try:
                    info = self._redis_client.info()
                    redis_info = {
                        'redis_version': info.get('redis_version', 'unknown'),
                        'used_memory': info.get('used_memory', 0),
                        'used_memory_human': info.get('used_memory_human', '0B'),
                        'connected_clients': info.get('connected_clients', 0),
                        'total_commands_processed': info.get('total_commands_processed', 0),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0),
                        'expired_keys': info.get('expired_keys', 0),
                        'evicted_keys': info.get('evicted_keys', 0)
                    }
                except Exception as e:
                    redis_info = {'error': str(e)}
            
            # Add backend-specific stats
            backend_stats = {
                'backend_type': 'redis',
                'connected': self._connected,
                'host': self.redis_config.host,
                'port': self.redis_config.port,
                'db': self.redis_config.db,
                'key_prefix': self.redis_config.key_prefix,
                'serialization_format': self.config.serialization_format.value,
                'compression_enabled': self.config.compression_enabled,
                'circuit_breaker_open': self._circuit_breaker_open,
                'circuit_breaker_failures': self._circuit_breaker_failures,
                'avg_operation_time': self._get_avg_operation_time(),
                'max_operation_time': max(self._operation_times) if self._operation_times else 0,
                'min_operation_time': min(self._operation_times) if self._operation_times else 0
            }
            
            return {
                **metrics_stats,
                **backend_stats,
                'redis_info': redis_info
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    # Async methods
    async def get_async(self, key: str) -> Optional[Any]:
        """Async version of get"""
        try:
            await self._initialize_async_connection()
            if not self._async_redis_client:
                return None
            
            start_time = time.time()
            redis_key = self._get_key(key)
            
            # Get serialized value from Redis
            serialized_value = await self._async_redis_client.get(redis_key)
            
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
            self.metrics.record_error(f"redis_async_get_error: {str(e)}")
            return None
    
    async def set_async(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Async version of set"""
        try:
            await self._initialize_async_connection()
            if not self._async_redis_client:
                return False
            
            start_time = time.time()
            redis_key = self._get_key(key)
            
            # Use configured TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            # Serialize value
            serialized_value = self.serializer.serialize(value)
            
            # Store in Redis with TTL
            if ttl and ttl > 0:
                success = await self._async_redis_client.setex(redis_key, int(ttl), serialized_value)
            else:
                success = await self._async_redis_client.set(redis_key, serialized_value)
            
            if success:
                # Record metrics
                operation_time = time.time() - start_time
                self.metrics.record_set()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
            
            return bool(success)
            
        except Exception as e:
            self.metrics.record_error(f"redis_async_set_error: {str(e)}")
            return False
    
    async def delete_async(self, key: str) -> bool:
        """Async version of delete"""
        try:
            await self._initialize_async_connection()
            if not self._async_redis_client:
                return False
            
            start_time = time.time()
            redis_key = self._get_key(key)
            
            deleted_count = await self._async_redis_client.delete(redis_key)
            success = deleted_count > 0
            
            if success:
                operation_time = time.time() - start_time
                self.metrics.record_delete()
                self.metrics.record_access_time(operation_time)
                self._record_operation_time(operation_time)
            
            return success
            
        except Exception as e:
            self.metrics.record_error(f"redis_async_delete_error: {str(e)}")
            return False
    
    async def exists_async(self, key: str) -> bool:
        """Async version of exists"""
        try:
            await self._initialize_async_connection()
            if not self._async_redis_client:
                return False
            
            redis_key = self._get_key(key)
            return bool(await self._async_redis_client.exists(redis_key))
            
        except Exception as e:
            self.metrics.record_error(f"redis_async_exists_error: {str(e)}")
            return False
    
    # Batch operations
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once using Redis pipeline"""
        if not self._ensure_connection():
            return {}
        
        try:
            redis_keys = [self._get_key(key) for key in keys]
            
            # Use pipeline for efficiency
            pipe = self._redis_client.pipeline()
            for redis_key in redis_keys:
                pipe.get(redis_key)
            
            results = pipe.execute()
            
            # Process results
            result = {}
            for i, (key, serialized_value) in enumerate(zip(keys, results)):
                if serialized_value is not None:
                    try:
                        value = self.serializer.deserialize(serialized_value)
                        result[key] = value
                        self.metrics.record_hit()
                    except Exception:
                        self.metrics.record_error(f"deserialize_error: {key}")
                else:
                    self.metrics.record_miss()
            
            return result
            
        except Exception as e:
            self.metrics.record_error(f"redis_get_many_error: {str(e)}")
            return {}
    
    def set_many(self, items: Dict[str, Any], ttl: Optional[float] = None) -> Dict[str, bool]:
        """Set multiple values at once using Redis pipeline"""
        if not self._ensure_connection():
            return {key: False for key in items.keys()}
        
        try:
            # Use configured TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            # Use pipeline for efficiency
            pipe = self._redis_client.pipeline()
            
            serialized_items = {}
            for key, value in items.items():
                try:
                    redis_key = self._get_key(key)
                    serialized_value = self.serializer.serialize(value)
                    serialized_items[key] = (redis_key, serialized_value)
                    
                    if ttl and ttl > 0:
                        pipe.setex(redis_key, int(ttl), serialized_value)
                    else:
                        pipe.set(redis_key, serialized_value)
                        
                except Exception as e:
                    self.metrics.record_error(f"serialize_error: {key}: {str(e)}")
            
            results = pipe.execute()
            
            # Process results
            result = {}
            for i, key in enumerate(serialized_items.keys()):
                success = bool(results[i]) if i < len(results) else False
                result[key] = success
                if success:
                    self.metrics.record_set()
            
            return result
            
        except Exception as e:
            self.metrics.record_error(f"redis_set_many_error: {str(e)}")
            return {key: False for key in items.keys()}
    
    def delete_many(self, keys: List[str]) -> Dict[str, bool]:
        """Delete multiple values at once using Redis pipeline"""
        if not self._ensure_connection():
            return {key: False for key in keys}
        
        try:
            redis_keys = [self._get_key(key) for key in keys]
            
            # Use pipeline for efficiency
            pipe = self._redis_client.pipeline()
            for redis_key in redis_keys:
                pipe.delete(redis_key)
            
            results = pipe.execute()
            
            # Process results
            result = {}
            for key, deleted_count in zip(keys, results):
                success = deleted_count > 0
                result[key] = success
                if success:
                    self.metrics.record_delete()
            
            return result
            
        except Exception as e:
            self.metrics.record_error(f"redis_delete_many_error: {str(e)}")
            return {key: False for key in keys}
    
    # Redis-specific operations
    def expire(self, key: str, ttl: float) -> bool:
        """Set TTL for an existing key"""
        if not self._ensure_connection():
            return False
        
        try:
            redis_key = self._get_key(key)
            return bool(self._redis_client.expire(redis_key, int(ttl)))
        except Exception as e:
            self.metrics.record_error(f"redis_expire_error: {str(e)}")
            return False
    
    def ttl(self, key: str) -> Optional[int]:
        """Get TTL for a key"""
        if not self._ensure_connection():
            return None
        
        try:
            redis_key = self._get_key(key)
            ttl_value = self._redis_client.ttl(redis_key)
            return ttl_value if ttl_value >= 0 else None
        except Exception as e:
            self.metrics.record_error(f"redis_ttl_error: {str(e)}")
            return None
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value"""
        if not self._ensure_connection():
            return None
        
        try:
            redis_key = self._get_key(key)
            return self._redis_client.incrby(redis_key, amount)
        except Exception as e:
            self.metrics.record_error(f"redis_increment_error: {str(e)}")
            return None
    
    def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement a numeric value"""
        if not self._ensure_connection():
            return None
        
        try:
            redis_key = self._get_key(key)
            return self._redis_client.decrby(redis_key, amount)
        except Exception as e:
            self.metrics.record_error(f"redis_decrement_error: {str(e)}")
            return None
    
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
        self._connected = False
        
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
        """Perform health check on the Redis backend"""
        try:
            # Test connection
            connection_healthy = self._ensure_connection()
            
            if not connection_healthy:
                return {
                    'healthy': False,
                    'backend_type': 'redis',
                    'error': 'Redis connection failed',
                    'connected': False
                }
            
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
            
            # Get Redis info
            redis_info = {}
            try:
                info = self._redis_client.info()
                redis_info = {
                    'version': info.get('redis_version', 'unknown'),
                    'used_memory': info.get('used_memory_human', '0B'),
                    'connected_clients': info.get('connected_clients', 0)
                }
            except Exception:
                redis_info = {'error': 'Could not get Redis info'}
            
            health_status = {
                'healthy': set_success and get_success and delete_success,
                'backend_type': 'redis',
                'connected': self._connected,
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
                'redis_info': redis_info,
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
                'backend_type': 'redis',
                'connected': self._connected
            }
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
        
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception:
                pass
        
        if self._async_redis_client:
            try:
                asyncio.create_task(self._async_redis_client.close())
            except Exception:
                pass
    
    def __del__(self):
        """Destructor"""
        try:
            if hasattr(self, '_thread_pool') and self._thread_pool:
                self._thread_pool.shutdown(wait=False)
            
            if hasattr(self, '_redis_client') and self._redis_client:
                self._redis_client.close()
        except Exception:
            pass  # Ignore errors during cleanup