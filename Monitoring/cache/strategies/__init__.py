"""Cache Strategies Module

Provides different caching strategies for the advanced caching system.
"""

from .base import CacheStrategy
from .lru import LRUCache
from .ttl import TTLCache
from .fifo import FIFOCache
from .lfu import LFUCache

__all__ = [
    'CacheStrategy',
    'LRUCache',
    'TTLCache', 
    'FIFOCache',
    'LFUCache'
]