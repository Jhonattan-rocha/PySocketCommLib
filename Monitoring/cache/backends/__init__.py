"""Cache Backends Module

This module provides different backend implementations for the caching system:
- MemoryBackend: In-memory cache using various strategies
- RedisBackend: Redis-based distributed cache

Backends handle the actual storage and retrieval of cached data,
while strategies define the eviction policies.
"""

from .memory import MemoryBackend
from .redis import RedisBackend

__all__ = [
    'MemoryBackend',
    'RedisBackend'
]