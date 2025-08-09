"""Advanced Caching System for PySocketCommLib Monitoring

This module provides a comprehensive caching solution with:
- Multiple caching strategies (LRU, TTL, FIFO)
- Redis and in-memory backends
- Performance metrics integration
- Async/sync operations support
- Cache warming and invalidation
- Decorators for easy usage
"""

from .cache_manager import CacheManager
from .decorators import cache, cache_result, cache_async
from .strategies.lru import LRUCache
from .strategies.ttl import TTLCache
from .strategies.fifo import FIFOCache
from .backends.memory import MemoryBackend
from .backends.redis import RedisBackend
from .metrics import CacheMetrics
from .config import CacheConfig

__all__ = [
    'CacheManager',
    'cache',
    'cache_result', 
    'cache_async',
    'LRUCache',
    'TTLCache',
    'FIFOCache',
    'MemoryBackend',
    'RedisBackend',
    'CacheMetrics',
    'CacheConfig'
]

__version__ = '1.0.0'