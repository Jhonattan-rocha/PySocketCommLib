"""Cache Configuration Module

Provides configuration classes and settings for the caching system.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class CacheStrategy(Enum):
    """Available cache strategies"""
    LRU = "lru"
    TTL = "ttl"
    FIFO = "fifo"
    LFU = "lfu"


class CacheBackend(Enum):
    """Available cache backends"""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class SerializationFormat(Enum):
    """Available serialization formats"""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


@dataclass
class RedisConfig:
    """Redis-specific configuration"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    max_connections: int = 10
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    
    @classmethod
    def from_env(cls) -> 'RedisConfig':
        """Create Redis config from environment variables"""
        return cls(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0')),
            password=os.getenv('REDIS_PASSWORD'),
            socket_timeout=float(os.getenv('REDIS_SOCKET_TIMEOUT', '5.0')),
            socket_connect_timeout=float(os.getenv('REDIS_CONNECT_TIMEOUT', '5.0')),
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '10'))
        )


@dataclass
class CacheConfig:
    """Main cache configuration"""
    # Strategy settings
    strategy: CacheStrategy = CacheStrategy.LRU
    backend: CacheBackend = CacheBackend.MEMORY
    
    # Size limits
    max_size: int = 1000
    max_memory_mb: int = 100
    
    # TTL settings
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400     # 24 hours
    
    # Performance settings
    enable_compression: bool = False
    compression_threshold: int = 1024  # bytes
    serialization_format: SerializationFormat = SerializationFormat.JSON
    
    # Monitoring settings
    enable_metrics: bool = True
    metrics_interval: int = 60  # seconds
    enable_detailed_logging: bool = False
    
    # Redis settings
    redis: RedisConfig = field(default_factory=RedisConfig)
    
    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    
    # Cache warming settings
    enable_warming: bool = False
    warming_batch_size: int = 100
    warming_delay: float = 0.1
    
    # Advanced settings
    enable_partitioning: bool = False
    partition_count: int = 4
    enable_async_operations: bool = True
    max_concurrent_operations: int = 4
    cleanup_interval: int = 300  # 5 minutes
    enable_background_cleanup: bool = True
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'CacheConfig':
        """Create config from dictionary"""
        redis_config = config_dict.pop('redis', {})
        if isinstance(redis_config, dict):
            redis_config = RedisConfig(**redis_config)
        
        # Convert string enums
        if 'strategy' in config_dict:
            config_dict['strategy'] = CacheStrategy(config_dict['strategy'])
        if 'backend' in config_dict:
            config_dict['backend'] = CacheBackend(config_dict['backend'])
        if 'serialization_format' in config_dict:
            config_dict['serialization_format'] = SerializationFormat(config_dict['serialization_format'])
        
        return cls(redis=redis_config, **config_dict)
    
    @classmethod
    def from_env(cls) -> 'CacheConfig':
        """Create config from environment variables"""
        return cls(
            strategy=CacheStrategy(os.getenv('CACHE_STRATEGY', 'lru')),
            backend=CacheBackend(os.getenv('CACHE_BACKEND', 'memory')),
            max_size=int(os.getenv('CACHE_MAX_SIZE', '1000')),
            max_memory_mb=int(os.getenv('CACHE_MAX_MEMORY_MB', '100')),
            default_ttl=int(os.getenv('CACHE_DEFAULT_TTL', '3600')),
            enable_compression=os.getenv('CACHE_ENABLE_COMPRESSION', 'false').lower() == 'true',
            enable_metrics=os.getenv('CACHE_ENABLE_METRICS', 'true').lower() == 'true',
            redis=RedisConfig.from_env()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        result = {
            'strategy': self.strategy.value,
            'backend': self.backend.value,
            'max_size': self.max_size,
            'max_memory_mb': self.max_memory_mb,
            'default_ttl': self.default_ttl,
            'max_ttl': self.max_ttl,
            'enable_compression': self.enable_compression,
            'compression_threshold': self.compression_threshold,
            'serialization_format': self.serialization_format.value,
            'enable_metrics': self.enable_metrics,
            'metrics_interval': self.metrics_interval,
            'enable_detailed_logging': self.enable_detailed_logging,
            'circuit_breaker_enabled': self.circuit_breaker_enabled,
            'circuit_breaker_failure_threshold': self.circuit_breaker_failure_threshold,
            'circuit_breaker_recovery_timeout': self.circuit_breaker_recovery_timeout,
            'enable_warming': self.enable_warming,
            'warming_batch_size': self.warming_batch_size,
            'warming_delay': self.warming_delay,
            'enable_partitioning': self.enable_partitioning,
            'partition_count': self.partition_count,
            'enable_async_operations': self.enable_async_operations,
            'max_concurrent_operations': self.max_concurrent_operations,
            'cleanup_interval': self.cleanup_interval,
            'enable_background_cleanup': self.enable_background_cleanup,
            'redis': {
                'host': self.redis.host,
                'port': self.redis.port,
                'db': self.redis.db,
                'password': self.redis.password,
                'socket_timeout': self.redis.socket_timeout,
                'socket_connect_timeout': self.redis.socket_connect_timeout,
                'max_connections': self.redis.max_connections,
                'retry_on_timeout': self.redis.retry_on_timeout,
                'health_check_interval': self.redis.health_check_interval
            }
        }
        return result


# Default configurations for different use cases
DEFAULT_CONFIGS = {
    'development': CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.MEMORY,
        max_size=500,
        enable_detailed_logging=True
    ),
    
    'production': CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.REDIS,
        max_size=10000,
        enable_compression=True,
        circuit_breaker_enabled=True
    ),
    
    'high_performance': CacheConfig(
        strategy=CacheStrategy.LRU,
        backend=CacheBackend.HYBRID,
        max_size=50000,
        enable_compression=True,
        enable_partitioning=True,
        serialization_format=SerializationFormat.MSGPACK
    )
}