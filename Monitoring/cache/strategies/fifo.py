"""FIFO (First In, First Out) Cache Strategy

Implements a cache that evicts the oldest entries when capacity is reached.
"""

import time
from typing import Any, Optional, List
from collections import deque
from .base import CacheStrategy, CacheEntry


class FIFOCache(CacheStrategy):
    """FIFO (First In, First Out) cache implementation
    
    This cache maintains entries in insertion order and evicts the
    oldest entries first when capacity is reached.
    """
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        super().__init__(max_size, max_memory_mb)
        # Use deque to maintain insertion order efficiently
        self._insertion_order = deque()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache (doesn't affect insertion order)"""
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        with self._lock:
            # Check if key already exists
            if key in self._entries:
                # Update existing entry (keep same position in queue)
                return self._update_entry(key, value, ttl)
            
            # Create new entry
            entry = self._create_entry(key, value, ttl)
            
            # Add entry (this handles eviction if needed)
            if self._add_entry(entry):
                self._insertion_order.append(key)
                return True
            
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        with self._lock:
            if self._remove_entry(key):
                # Remove from insertion order queue
                try:
                    self._insertion_order.remove(key)
                except ValueError:
                    # Key not in queue (shouldn't happen, but handle gracefully)
                    pass
                return True
            return False
    
    def _evict(self) -> List[str]:
        """Evict the oldest entry (first in)"""
        if not self._insertion_order:
            return []
        
        # Get the oldest key (first in queue)
        oldest_key = self._insertion_order.popleft()
        
        # Remove from entries
        self._remove_entry(oldest_key)
        
        return [oldest_key]
    
    def clear(self):
        """Clear all entries from the cache"""
        with self._lock:
            super().clear()
            self._insertion_order.clear()
    
    def _remove_entry(self, key: str) -> bool:
        """Remove entry from cache and insertion order"""
        result = super()._remove_entry(key)
        if result:
            try:
                self._insertion_order.remove(key)
            except ValueError:
                # Key not in queue (shouldn't happen, but handle gracefully)
                pass
        return result
    
    def get_insertion_order(self) -> List[str]:
        """Get keys in insertion order (oldest first)"""
        with self._lock:
            self._cleanup_expired()
            # Filter out keys that no longer exist in entries
            valid_keys = [key for key in self._insertion_order if key in self._entries]
            # Update insertion order to remove stale keys
            self._insertion_order = deque(valid_keys)
            return list(self._insertion_order)
    
    def get_oldest_entries(self, count: int = 10) -> List[dict]:
        """Get information about the oldest entries"""
        with self._lock:
            self._cleanup_expired()
            oldest_keys = list(self._insertion_order)[:count]
            
            oldest_entries = []
            for key in oldest_keys:
                if key in self._entries:
                    entry = self._entries[key]
                    oldest_entries.append({
                        'key': key,
                        'created_at': entry.created_at,
                        'age': entry.age,
                        'size': entry.size,
                        'access_count': entry.access_count,
                        'last_accessed': entry.accessed_at
                    })
            
            return oldest_entries
    
    def get_newest_entries(self, count: int = 10) -> List[dict]:
        """Get information about the newest entries"""
        with self._lock:
            self._cleanup_expired()
            # Get keys from the end of the deque (newest)
            newest_keys = list(self._insertion_order)[-count:]
            newest_keys.reverse()  # Most recent first
            
            newest_entries = []
            for key in newest_keys:
                if key in self._entries:
                    entry = self._entries[key]
                    newest_entries.append({
                        'key': key,
                        'created_at': entry.created_at,
                        'age': entry.age,
                        'size': entry.size,
                        'access_count': entry.access_count,
                        'last_accessed': entry.accessed_at
                    })
            
            return newest_entries
    
    def peek_oldest(self) -> Optional[str]:
        """Peek at the oldest key without removing it"""
        with self._lock:
            if not self._insertion_order:
                return None
            return self._insertion_order[0]
    
    def peek_newest(self) -> Optional[str]:
        """Peek at the newest key without removing it"""
        with self._lock:
            if not self._insertion_order:
                return None
            return self._insertion_order[-1]
    
    def get_age_distribution(self) -> dict:
        """Get distribution of entry ages"""
        with self._lock:
            self._cleanup_expired()
            
            if not self._entries:
                return {
                    'total_entries': 0,
                    'distribution': {},
                    'avg_age': 0,
                    'oldest_age': 0,
                    'newest_age': 0
                }
            
            current_time = time.time()
            ages = []
            distribution = {
                '0-1m': 0, '1-5m': 0, '5-30m': 0, '30m-1h': 0,
                '1-6h': 0, '6-24h': 0, '1d+': 0
            }
            
            for entry in self._entries.values():
                age_seconds = current_time - entry.created_at
                ages.append(age_seconds)
                
                age_minutes = age_seconds / 60
                if age_minutes < 1:
                    distribution['0-1m'] += 1
                elif age_minutes < 5:
                    distribution['1-5m'] += 1
                elif age_minutes < 30:
                    distribution['5-30m'] += 1
                elif age_minutes < 60:
                    distribution['30m-1h'] += 1
                elif age_minutes < 360:  # 6 hours
                    distribution['1-6h'] += 1
                elif age_minutes < 1440:  # 24 hours
                    distribution['6-24h'] += 1
                else:
                    distribution['1d+'] += 1
            
            return {
                'total_entries': len(self._entries),
                'distribution': distribution,
                'avg_age': sum(ages) / len(ages),
                'oldest_age': max(ages),
                'newest_age': min(ages)
            }
    
    def get_insertion_rate(self, time_window_seconds: int = 3600) -> dict:
        """Get insertion rate statistics over a time window"""
        with self._lock:
            self._cleanup_expired()
            current_time = time.time()
            window_start = current_time - time_window_seconds
            
            # Count entries inserted within the time window
            recent_entries = 0
            for entry in self._entries.values():
                if entry.created_at >= window_start:
                    recent_entries += 1
            
            insertion_rate = recent_entries / (time_window_seconds / 3600)  # per hour
            
            return {
                'time_window_hours': time_window_seconds / 3600,
                'entries_in_window': recent_entries,
                'insertion_rate_per_hour': insertion_rate,
                'total_entries': len(self._entries)
            }
    
    def predict_eviction_time(self, key: str) -> Optional[float]:
        """Predict when a key might be evicted based on current insertion rate"""
        with self._lock:
            if key not in self._entries or key not in self._insertion_order:
                return None
            
            # Find position of key in insertion order
            key_position = list(self._insertion_order).index(key)
            
            # Calculate recent insertion rate
            rate_stats = self.get_insertion_rate(3600)  # Last hour
            insertion_rate_per_second = rate_stats['insertion_rate_per_hour'] / 3600
            
            if insertion_rate_per_second <= 0:
                return None  # No recent activity
            
            # Calculate how many more entries can fit
            remaining_capacity = self.max_size - len(self._entries)
            
            # If cache is not full, estimate time until it fills up
            if remaining_capacity > 0:
                time_to_fill = remaining_capacity / insertion_rate_per_second
                # After cache fills, this key will be evicted after key_position more insertions
                additional_time = key_position / insertion_rate_per_second
                return time_to_fill + additional_time
            else:
                # Cache is full, key will be evicted after key_position more insertions
                return key_position / insertion_rate_per_second
    
    def get_eviction_candidates(self, count: int = 10) -> List[dict]:
        """Get entries that are most likely to be evicted soon"""
        with self._lock:
            self._cleanup_expired()
            candidates = []
            
            # Get oldest entries (first candidates for eviction)
            oldest_keys = list(self._insertion_order)[:count]
            
            for i, key in enumerate(oldest_keys):
                if key in self._entries:
                    entry = self._entries[key]
                    predicted_eviction = self.predict_eviction_time(key)
                    
                    candidates.append({
                        'key': key,
                        'position_in_queue': i,
                        'age': entry.age,
                        'size': entry.size,
                        'access_count': entry.access_count,
                        'predicted_eviction_seconds': predicted_eviction,
                        'created_at': entry.created_at
                    })
            
            return candidates
    
    def optimize_queue(self) -> dict:
        """Optimize the insertion order queue by removing stale entries"""
        with self._lock:
            initial_size = len(self._insertion_order)
            
            # Rebuild queue with only valid keys
            valid_keys = [key for key in self._insertion_order if key in self._entries]
            self._insertion_order = deque(valid_keys)
            
            final_size = len(self._insertion_order)
            
            return {
                'initial_queue_size': initial_size,
                'final_queue_size': final_size,
                'stale_entries_removed': initial_size - final_size,
                'entries_count': len(self._entries)
            }
    
    def get_queue_integrity(self) -> dict:
        """Check the integrity of the insertion order queue"""
        with self._lock:
            queue_keys = set(self._insertion_order)
            entry_keys = set(self._entries.keys())
            
            # Keys in queue but not in entries (stale)
            stale_in_queue = queue_keys - entry_keys
            
            # Keys in entries but not in queue (missing)
            missing_from_queue = entry_keys - queue_keys
            
            return {
                'queue_size': len(self._insertion_order),
                'entries_size': len(self._entries),
                'stale_in_queue': len(stale_in_queue),
                'missing_from_queue': len(missing_from_queue),
                'integrity_ok': len(stale_in_queue) == 0 and len(missing_from_queue) == 0,
                'stale_keys': list(stale_in_queue)[:10],  # First 10 for debugging
                'missing_keys': list(missing_from_queue)[:10]  # First 10 for debugging
            }