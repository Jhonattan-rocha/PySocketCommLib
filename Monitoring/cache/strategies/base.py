"""Base Cache Strategy Module

Provides the abstract base class for all cache strategies.
"""

import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Tuple, Iterator
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    size: int = 0
    ttl: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.accessed_at is None:
            self.accessed_at = self.created_at
    
    @property
    def age(self) -> float:
        """Get the age of the entry in seconds"""
        return time.time() - self.created_at
    
    @property
    def time_since_access(self) -> float:
        """Get time since last access in seconds"""
        return time.time() - self.accessed_at
    
    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired based on TTL"""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)
    
    def touch(self):
        """Update access time and increment access count"""
        self.accessed_at = time.time()
        self.access_count += 1
    
    def estimate_size(self) -> int:
        """Estimate the memory size of this entry"""
        if self.size > 0:
            return self.size
        
        # Basic size estimation
        import sys
        try:
            key_size = sys.getsizeof(self.key)
            value_size = sys.getsizeof(self.value)
            metadata_size = sys.getsizeof(self.created_at) + sys.getsizeof(self.accessed_at) + \
                          sys.getsizeof(self.access_count) + sys.getsizeof(self.ttl)
            return key_size + value_size + metadata_size
        except (TypeError, OverflowError):
            # Fallback for objects that can't be sized
            return len(str(self.value).encode('utf-8')) + len(str(self.key).encode('utf-8'))


class CacheStrategy(ABC):
    """Abstract base class for cache strategies"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._lock = threading.RLock()
        self._entries: Dict[str, CacheEntry] = {}
        self._current_memory = 0
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        pass
    
    @abstractmethod
    def _evict(self) -> List[str]:
        """Evict entries according to the strategy. Returns list of evicted keys."""
        pass
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache"""
        with self._lock:
            if key not in self._entries:
                return False
            
            entry = self._entries[key]
            if entry.is_expired:
                self._remove_entry(key)
                return False
            
            return True
    
    def size(self) -> int:
        """Get the number of entries in the cache"""
        with self._lock:
            self._cleanup_expired()
            return len(self._entries)
    
    def memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        with self._lock:
            return self._current_memory
    
    def clear(self):
        """Clear all entries from the cache"""
        with self._lock:
            self._entries.clear()
            self._current_memory = 0
    
    def keys(self) -> List[str]:
        """Get all keys in the cache"""
        with self._lock:
            self._cleanup_expired()
            return list(self._entries.keys())
    
    def items(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over cache items"""
        with self._lock:
            self._cleanup_expired()
            for key, entry in self._entries.items():
                yield key, entry.value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'size': len(self._entries),
                'max_size': self.max_size,
                'memory_usage': self._current_memory,
                'max_memory': self.max_memory_bytes,
                'hits': self._hits,
                'misses': self._misses,
                'evictions': self._evictions,
                'hit_rate': hit_rate,
                'memory_utilization': self._current_memory / self.max_memory_bytes if self.max_memory_bytes > 0 else 0.0
            }
    
    def _get_entry(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry, handling expiration"""
        if key not in self._entries:
            self._misses += 1
            return None
        
        entry = self._entries[key]
        if entry.is_expired:
            self._remove_entry(key)
            self._misses += 1
            return None
        
        entry.touch()
        self._hits += 1
        return entry
    
    def _create_entry(self, key: str, value: Any, ttl: Optional[float] = None) -> CacheEntry:
        """Create a new cache entry"""
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            accessed_at=time.time(),
            ttl=ttl
        )
        entry.size = entry.estimate_size()
        return entry
    
    def _add_entry(self, entry: CacheEntry) -> bool:
        """Add entry to cache, handling size limits"""
        # Check if we need to evict entries
        while (len(self._entries) >= self.max_size or 
               self._current_memory + entry.size > self.max_memory_bytes):
            evicted_keys = self._evict()
            if not evicted_keys:
                # Can't evict anything, cache is full
                return False
            self._evictions += len(evicted_keys)
        
        # Add the entry
        self._entries[entry.key] = entry
        self._current_memory += entry.size
        return True
    
    def _remove_entry(self, key: str) -> bool:
        """Remove entry from cache"""
        if key in self._entries:
            entry = self._entries.pop(key)
            self._current_memory -= entry.size
            return True
        return False
    
    def _update_entry(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Update existing entry"""
        if key not in self._entries:
            return False
        
        old_entry = self._entries[key]
        old_size = old_entry.size
        
        # Create new entry with updated value
        new_entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            accessed_at=time.time(),
            access_count=old_entry.access_count,
            ttl=ttl
        )
        new_entry.size = new_entry.estimate_size()
        
        # Check if new size fits
        size_diff = new_entry.size - old_size
        if size_diff > 0 and self._current_memory + size_diff > self.max_memory_bytes:
            # Try to evict some entries to make room
            while self._current_memory + size_diff > self.max_memory_bytes:
                evicted_keys = self._evict()
                if not evicted_keys or key in evicted_keys:
                    # Can't make room or we evicted ourselves
                    return False
                self._evictions += len(evicted_keys)
        
        # Update the entry
        self._entries[key] = new_entry
        self._current_memory += size_diff
        return True
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        expired_keys = []
        for key, entry in self._entries.items():
            if entry.is_expired:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
    
    def _should_evict(self) -> bool:
        """Check if eviction is needed"""
        return (len(self._entries) >= self.max_size or 
                self._current_memory >= self.max_memory_bytes)
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a cache entry"""
        with self._lock:
            if key not in self._entries:
                return None
            
            entry = self._entries[key]
            return {
                'key': entry.key,
                'size': entry.size,
                'created_at': entry.created_at,
                'accessed_at': entry.accessed_at,
                'access_count': entry.access_count,
                'age': entry.age,
                'time_since_access': entry.time_since_access,
                'ttl': entry.ttl,
                'is_expired': entry.is_expired
            }
    
    def get_all_entries_info(self) -> List[Dict[str, Any]]:
        """Get information about all cache entries"""
        with self._lock:
            self._cleanup_expired()
            return [self.get_entry_info(key) for key in self._entries.keys()]
    
    @property
    def strategy_name(self) -> str:
        """Get the name of this strategy"""
        return self.__class__.__name__