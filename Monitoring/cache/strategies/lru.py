"""LRU (Least Recently Used) Cache Strategy

Implements a cache that evicts the least recently used items when capacity is reached.
"""

import time
from typing import Any, Optional, List
from collections import OrderedDict
from .base import CacheStrategy, CacheEntry


class LRUCache(CacheStrategy):
    """LRU (Least Recently Used) cache implementation
    
    This cache maintains items in order of access, with the most recently
    accessed items at the end. When eviction is needed, items from the
    beginning (least recently used) are removed first.
    """
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        super().__init__(max_size, max_memory_mb)
        # Use OrderedDict to maintain access order
        self._access_order = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache, updating its position in LRU order"""
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return None
            
            # Move to end (most recently used)
            self._access_order.move_to_end(key)
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        with self._lock:
            # Check if key already exists
            if key in self._entries:
                # Update existing entry
                if self._update_entry(key, value, ttl):
                    self._access_order.move_to_end(key)
                    return True
                return False
            
            # Create new entry
            entry = self._create_entry(key, value, ttl)
            
            # Add entry (this handles eviction if needed)
            if self._add_entry(entry):
                self._access_order[key] = None  # Value doesn't matter, just order
                return True
            
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        with self._lock:
            if self._remove_entry(key):
                self._access_order.pop(key, None)
                return True
            return False
    
    def _evict(self) -> List[str]:
        """Evict the least recently used entry"""
        if not self._access_order:
            return []
        
        # Get the least recently used key (first in OrderedDict)
        lru_key = next(iter(self._access_order))
        
        # Remove from both structures
        self._remove_entry(lru_key)
        self._access_order.pop(lru_key, None)
        
        return [lru_key]
    
    def clear(self):
        """Clear all entries from the cache"""
        with self._lock:
            super().clear()
            self._access_order.clear()
    
    def _remove_entry(self, key: str) -> bool:
        """Remove entry from cache and access order"""
        result = super()._remove_entry(key)
        if result:
            self._access_order.pop(key, None)
        return result
    
    def get_lru_info(self) -> List[dict]:
        """Get information about entries in LRU order"""
        with self._lock:
            self._cleanup_expired()
            lru_info = []
            
            for key in self._access_order:
                if key in self._entries:
                    entry = self._entries[key]
                    lru_info.append({
                        'key': key,
                        'accessed_at': entry.accessed_at,
                        'access_count': entry.access_count,
                        'size': entry.size,
                        'age': entry.age,
                        'time_since_access': entry.time_since_access
                    })
            
            return lru_info
    
    def get_most_used(self, count: int = 10) -> List[dict]:
        """Get the most frequently accessed entries"""
        with self._lock:
            self._cleanup_expired()
            
            # Sort by access count (descending)
            entries_by_usage = sorted(
                [(key, entry) for key, entry in self._entries.items()],
                key=lambda x: x[1].access_count,
                reverse=True
            )
            
            return [{
                'key': key,
                'access_count': entry.access_count,
                'accessed_at': entry.accessed_at,
                'size': entry.size,
                'hit_rate': entry.access_count / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
            } for key, entry in entries_by_usage[:count]]
    
    def get_least_used(self, count: int = 10) -> List[dict]:
        """Get the least frequently accessed entries"""
        with self._lock:
            self._cleanup_expired()
            
            # Sort by access count (ascending)
            entries_by_usage = sorted(
                [(key, entry) for key, entry in self._entries.items()],
                key=lambda x: x[1].access_count
            )
            
            return [{
                'key': key,
                'access_count': entry.access_count,
                'accessed_at': entry.accessed_at,
                'size': entry.size,
                'time_since_access': entry.time_since_access
            } for key, entry in entries_by_usage[:count]]
    
    def peek_lru(self) -> Optional[str]:
        """Peek at the least recently used key without affecting order"""
        with self._lock:
            if not self._access_order:
                return None
            return next(iter(self._access_order))
    
    def peek_mru(self) -> Optional[str]:
        """Peek at the most recently used key without affecting order"""
        with self._lock:
            if not self._access_order:
                return None
            return next(reversed(self._access_order))
    
    def promote(self, key: str) -> bool:
        """Promote a key to most recently used without accessing its value"""
        with self._lock:
            if key not in self._entries:
                return False
            
            entry = self._entries[key]
            if entry.is_expired:
                self._remove_entry(key)
                return False
            
            # Update access time and move to end
            entry.touch()
            self._access_order.move_to_end(key)
            return True
    
    def get_access_pattern(self) -> dict:
        """Get access pattern statistics"""
        with self._lock:
            self._cleanup_expired()
            
            if not self._entries:
                return {
                    'total_entries': 0,
                    'avg_access_count': 0,
                    'access_distribution': {},
                    'temporal_distribution': {}
                }
            
            # Calculate access statistics
            access_counts = [entry.access_count for entry in self._entries.values()]
            avg_access_count = sum(access_counts) / len(access_counts)
            
            # Access count distribution
            access_distribution = {}
            for count in access_counts:
                range_key = f"{(count // 10) * 10}-{(count // 10) * 10 + 9}"
                access_distribution[range_key] = access_distribution.get(range_key, 0) + 1
            
            # Temporal distribution (entries by age)
            current_time = time.time()
            temporal_distribution = {
                '0-1h': 0, '1-6h': 0, '6-24h': 0, '1-7d': 0, '7d+': 0
            }
            
            for entry in self._entries.values():
                age_hours = (current_time - entry.created_at) / 3600
                if age_hours < 1:
                    temporal_distribution['0-1h'] += 1
                elif age_hours < 6:
                    temporal_distribution['1-6h'] += 1
                elif age_hours < 24:
                    temporal_distribution['6-24h'] += 1
                elif age_hours < 168:  # 7 days
                    temporal_distribution['1-7d'] += 1
                else:
                    temporal_distribution['7d+'] += 1
            
            return {
                'total_entries': len(self._entries),
                'avg_access_count': avg_access_count,
                'access_distribution': access_distribution,
                'temporal_distribution': temporal_distribution,
                'lru_key': self.peek_lru(),
                'mru_key': self.peek_mru()
            }
    
    def optimize(self) -> dict:
        """Optimize the cache by removing expired entries and analyzing patterns"""
        with self._lock:
            initial_size = len(self._entries)
            initial_memory = self._current_memory
            
            # Clean up expired entries
            self._cleanup_expired()
            
            # Remove entries that haven't been accessed in a long time
            current_time = time.time()
            stale_threshold = 24 * 3600  # 24 hours
            stale_keys = []
            
            for key, entry in self._entries.items():
                if current_time - entry.accessed_at > stale_threshold and entry.access_count < 2:
                    stale_keys.append(key)
            
            # Remove stale entries (but keep at least 50% of cache)
            max_removals = len(self._entries) // 2
            removed_stale = 0
            
            for key in stale_keys[:max_removals]:
                if self._remove_entry(key):
                    removed_stale += 1
            
            final_size = len(self._entries)
            final_memory = self._current_memory
            
            return {
                'initial_size': initial_size,
                'final_size': final_size,
                'entries_removed': initial_size - final_size,
                'stale_entries_removed': removed_stale,
                'memory_freed_bytes': initial_memory - final_memory,
                'memory_freed_mb': (initial_memory - final_memory) / 1024 / 1024
            }