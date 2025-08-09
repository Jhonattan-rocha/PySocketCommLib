"""TTL (Time To Live) Cache Strategy

Implements a cache where entries expire after a specified time period.
"""

import time
import heapq
from typing import Any, Optional, List, Tuple
from .base import CacheStrategy, CacheEntry


class TTLCache(CacheStrategy):
    """TTL (Time To Live) cache implementation
    
    This cache automatically expires entries after their TTL period.
    Uses a min-heap to efficiently track and remove expired entries.
    """
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100, 
                 default_ttl: float = 3600):
        super().__init__(max_size, max_memory_mb)
        self.default_ttl = default_ttl
        
        # Min-heap to track expiration times: (expiration_time, key)
        self._expiration_heap: List[Tuple[float, str]] = []
        
        # Track which entries are in the heap to avoid duplicates
        self._heap_entries = set()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache"""
        with self._lock:
            # Clean up expired entries first
            self._cleanup_expired()
            
            entry = self._get_entry(key)
            if entry is None:
                return None
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache with TTL"""
        with self._lock:
            if ttl is None:
                ttl = self.default_ttl
            
            # Remove existing entry if it exists
            if key in self._entries:
                self._remove_from_heap(key)
                if not self._update_entry(key, value, ttl):
                    return False
            else:
                # Create new entry
                entry = self._create_entry(key, value, ttl)
                if not self._add_entry(entry):
                    return False
            
            # Add to expiration heap
            expiration_time = time.time() + ttl
            heapq.heappush(self._expiration_heap, (expiration_time, key))
            self._heap_entries.add(key)
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        with self._lock:
            if self._remove_entry(key):
                self._remove_from_heap(key)
                return True
            return False
    
    def _evict(self) -> List[str]:
        """Evict expired entries first, then oldest entries"""
        # First try to evict expired entries
        expired_keys = self._cleanup_expired()
        if expired_keys:
            return expired_keys
        
        # If no expired entries, evict the oldest entry
        if not self._entries:
            return []
        
        # Find the oldest entry by creation time
        oldest_key = min(self._entries.keys(), 
                        key=lambda k: self._entries[k].created_at)
        
        self._remove_entry(oldest_key)
        self._remove_from_heap(oldest_key)
        
        return [oldest_key]
    
    def _cleanup_expired(self) -> List[str]:
        """Remove all expired entries and return their keys"""
        current_time = time.time()
        expired_keys = []
        
        # Process expiration heap
        while self._expiration_heap:
            expiration_time, key = self._expiration_heap[0]
            
            if expiration_time > current_time:
                # No more expired entries
                break
            
            # Remove from heap
            heapq.heappop(self._expiration_heap)
            self._heap_entries.discard(key)
            
            # Check if entry still exists and is actually expired
            if key in self._entries:
                entry = self._entries[key]
                if entry.is_expired:
                    self._remove_entry(key)
                    expired_keys.append(key)
        
        return expired_keys
    
    def _remove_from_heap(self, key: str):
        """Remove a key from the expiration heap tracking"""
        self._heap_entries.discard(key)
        # Note: We don't actually remove from heap as it's expensive
        # The cleanup process will handle stale entries
    
    def clear(self):
        """Clear all entries from the cache"""
        with self._lock:
            super().clear()
            self._expiration_heap.clear()
            self._heap_entries.clear()
    
    def get_ttl(self, key: str) -> Optional[float]:
        """Get the remaining TTL for a key in seconds"""
        with self._lock:
            if key not in self._entries:
                return None
            
            entry = self._entries[key]
            if entry.ttl is None:
                return None
            
            remaining = (entry.created_at + entry.ttl) - time.time()
            return max(0, remaining)
    
    def extend_ttl(self, key: str, additional_seconds: float) -> bool:
        """Extend the TTL of an existing entry"""
        with self._lock:
            if key not in self._entries:
                return False
            
            entry = self._entries[key]
            if entry.ttl is None:
                return False
            
            # Update TTL
            entry.ttl += additional_seconds
            
            # Add new expiration time to heap
            new_expiration = time.time() + self.get_ttl(key)
            heapq.heappush(self._expiration_heap, (new_expiration, key))
            self._heap_entries.add(key)
            
            return True
    
    def refresh_ttl(self, key: str, new_ttl: Optional[float] = None) -> bool:
        """Reset the TTL of an existing entry"""
        with self._lock:
            if key not in self._entries:
                return False
            
            if new_ttl is None:
                new_ttl = self.default_ttl
            
            entry = self._entries[key]
            entry.created_at = time.time()
            entry.ttl = new_ttl
            
            # Add new expiration time to heap
            expiration_time = time.time() + new_ttl
            heapq.heappush(self._expiration_heap, (expiration_time, key))
            self._heap_entries.add(key)
            
            return True
    
    def get_expiring_soon(self, threshold_seconds: float = 300) -> List[dict]:
        """Get entries that will expire within the threshold"""
        with self._lock:
            self._cleanup_expired()
            current_time = time.time()
            expiring_soon = []
            
            for key, entry in self._entries.items():
                if entry.ttl is not None:
                    expiration_time = entry.created_at + entry.ttl
                    time_to_expire = expiration_time - current_time
                    
                    if 0 < time_to_expire <= threshold_seconds:
                        expiring_soon.append({
                            'key': key,
                            'time_to_expire': time_to_expire,
                            'expiration_time': expiration_time,
                            'size': entry.size,
                            'access_count': entry.access_count
                        })
            
            # Sort by time to expire (ascending)
            expiring_soon.sort(key=lambda x: x['time_to_expire'])
            return expiring_soon
    
    def get_ttl_distribution(self) -> dict:
        """Get distribution of TTL values across all entries"""
        with self._lock:
            self._cleanup_expired()
            
            if not self._entries:
                return {'total_entries': 0, 'distribution': {}}
            
            current_time = time.time()
            distribution = {
                '0-5m': 0, '5-30m': 0, '30m-1h': 0, 
                '1-6h': 0, '6-24h': 0, '1d+': 0, 'no_ttl': 0
            }
            
            for entry in self._entries.values():
                if entry.ttl is None:
                    distribution['no_ttl'] += 1
                    continue
                
                remaining_ttl = (entry.created_at + entry.ttl) - current_time
                remaining_minutes = remaining_ttl / 60
                
                if remaining_minutes < 5:
                    distribution['0-5m'] += 1
                elif remaining_minutes < 30:
                    distribution['5-30m'] += 1
                elif remaining_minutes < 60:
                    distribution['30m-1h'] += 1
                elif remaining_minutes < 360:  # 6 hours
                    distribution['1-6h'] += 1
                elif remaining_minutes < 1440:  # 24 hours
                    distribution['6-24h'] += 1
                else:
                    distribution['1d+'] += 1
            
            return {
                'total_entries': len(self._entries),
                'distribution': distribution,
                'avg_ttl': self._calculate_avg_ttl()
            }
    
    def _calculate_avg_ttl(self) -> float:
        """Calculate average remaining TTL across all entries"""
        current_time = time.time()
        ttl_values = []
        
        for entry in self._entries.values():
            if entry.ttl is not None:
                remaining = (entry.created_at + entry.ttl) - current_time
                if remaining > 0:
                    ttl_values.append(remaining)
        
        return sum(ttl_values) / len(ttl_values) if ttl_values else 0
    
    def schedule_cleanup(self, interval_seconds: float = 60):
        """Schedule periodic cleanup of expired entries"""
        import threading
        
        def cleanup_worker():
            while True:
                time.sleep(interval_seconds)
                with self._lock:
                    expired_count = len(self._cleanup_expired())
                    if expired_count > 0:
                        # Log cleanup activity if needed
                        pass
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        return cleanup_thread
    
    def get_heap_stats(self) -> dict:
        """Get statistics about the expiration heap"""
        with self._lock:
            heap_size = len(self._expiration_heap)
            active_entries = len(self._heap_entries)
            stale_entries = heap_size - active_entries
            
            # Calculate next expiration time
            next_expiration = None
            if self._expiration_heap:
                next_expiration = self._expiration_heap[0][0]
            
            return {
                'heap_size': heap_size,
                'active_entries': active_entries,
                'stale_entries': stale_entries,
                'next_expiration': next_expiration,
                'time_to_next_expiration': (next_expiration - time.time()) if next_expiration else None
            }
    
    def compact_heap(self) -> dict:
        """Compact the expiration heap by removing stale entries"""
        with self._lock:
            initial_size = len(self._expiration_heap)
            
            # Rebuild heap with only valid entries
            new_heap = []
            current_time = time.time()
            
            for expiration_time, key in self._expiration_heap:
                if (key in self._heap_entries and 
                    key in self._entries and 
                    expiration_time > current_time):
                    new_heap.append((expiration_time, key))
            
            # Replace old heap
            self._expiration_heap = new_heap
            heapq.heapify(self._expiration_heap)
            
            final_size = len(self._expiration_heap)
            
            return {
                'initial_size': initial_size,
                'final_size': final_size,
                'entries_removed': initial_size - final_size,
                'compression_ratio': final_size / initial_size if initial_size > 0 else 1.0
            }