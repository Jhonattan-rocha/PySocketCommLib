"""LFU (Least Frequently Used) Cache Strategy

Implements a cache that evicts the least frequently used entries when capacity is reached.
"""

import time
import heapq
from typing import Any, Optional, List, Dict
from collections import defaultdict, Counter
from .base import CacheStrategy, CacheEntry


class LFUCache(CacheStrategy):
    """LFU (Least Frequently Used) cache implementation
    
    This cache maintains access frequency for each entry and evicts the
    least frequently used entries first when capacity is reached.
    """
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        super().__init__(max_size, max_memory_mb)
        # Min-heap to track frequencies: (frequency, timestamp, key)
        self._frequency_heap = []
        # Track current frequency for each key
        self._key_frequencies = {}
        # Counter for tie-breaking (when frequencies are equal, use timestamp)
        self._timestamp_counter = 0
        # Track frequency distribution
        self._frequency_distribution = defaultdict(int)
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache and update its frequency"""
        with self._lock:
            entry = self._get_entry(key)
            if entry is None:
                return None
            
            # Update frequency
            self._update_frequency(key)
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache"""
        with self._lock:
            # Check if key already exists
            if key in self._entries:
                # Update existing entry (frequency remains the same)
                return self._update_entry(key, value, ttl)
            
            # Create new entry
            entry = self._create_entry(key, value, ttl)
            
            # Add entry (this handles eviction if needed)
            if self._add_entry(entry):
                # Initialize frequency for new key
                self._key_frequencies[key] = 1
                self._frequency_distribution[1] += 1
                
                # Add to frequency heap
                self._timestamp_counter += 1
                heapq.heappush(self._frequency_heap, (1, self._timestamp_counter, key))
                
                return True
            
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache"""
        with self._lock:
            if self._remove_entry(key):
                # Remove frequency tracking
                if key in self._key_frequencies:
                    old_freq = self._key_frequencies[key]
                    self._frequency_distribution[old_freq] -= 1
                    if self._frequency_distribution[old_freq] <= 0:
                        del self._frequency_distribution[old_freq]
                    del self._key_frequencies[key]
                
                # Note: We don't remove from heap immediately for efficiency
                # Stale entries will be filtered out during eviction
                return True
            return False
    
    def _evict(self) -> List[str]:
        """Evict the least frequently used entry"""
        # Clean up stale entries from heap
        while self._frequency_heap:
            freq, timestamp, key = heapq.heappop(self._frequency_heap)
            
            # Check if this entry is still valid
            if (key in self._entries and 
                key in self._key_frequencies and 
                self._key_frequencies[key] == freq):
                
                # This is the least frequently used entry
                self._remove_entry(key)
                
                # Remove frequency tracking
                self._frequency_distribution[freq] -= 1
                if self._frequency_distribution[freq] <= 0:
                    del self._frequency_distribution[freq]
                del self._key_frequencies[key]
                
                return [key]
        
        # If heap is empty but we still have entries, rebuild heap
        if self._entries:
            self._rebuild_frequency_heap()
            return self._evict()  # Try again
        
        return []
    
    def clear(self):
        """Clear all entries from the cache"""
        with self._lock:
            super().clear()
            self._frequency_heap.clear()
            self._key_frequencies.clear()
            self._frequency_distribution.clear()
            self._timestamp_counter = 0
    
    def _remove_entry(self, key: str) -> bool:
        """Remove entry from cache and frequency tracking"""
        result = super()._remove_entry(key)
        if result and key in self._key_frequencies:
            old_freq = self._key_frequencies[key]
            self._frequency_distribution[old_freq] -= 1
            if self._frequency_distribution[old_freq] <= 0:
                del self._frequency_distribution[old_freq]
            del self._key_frequencies[key]
        return result
    
    def _update_frequency(self, key: str):
        """Update the access frequency for a key"""
        if key not in self._key_frequencies:
            return
        
        old_freq = self._key_frequencies[key]
        new_freq = old_freq + 1
        
        # Update frequency tracking
        self._key_frequencies[key] = new_freq
        
        # Update distribution
        self._frequency_distribution[old_freq] -= 1
        if self._frequency_distribution[old_freq] <= 0:
            del self._frequency_distribution[old_freq]
        self._frequency_distribution[new_freq] += 1
        
        # Add new entry to heap (old entries will be filtered out)
        self._timestamp_counter += 1
        heapq.heappush(self._frequency_heap, (new_freq, self._timestamp_counter, key))
    
    def _rebuild_frequency_heap(self):
        """Rebuild the frequency heap from current state"""
        self._frequency_heap.clear()
        self._timestamp_counter = 0
        
        for key, freq in self._key_frequencies.items():
            if key in self._entries:
                self._timestamp_counter += 1
                heapq.heappush(self._frequency_heap, (freq, self._timestamp_counter, key))
    
    def get_frequency_distribution(self) -> Dict[int, int]:
        """Get the distribution of access frequencies"""
        with self._lock:
            self._cleanup_expired()
            return dict(self._frequency_distribution)
    
    def get_least_frequent_entries(self, count: int = 10) -> List[dict]:
        """Get information about the least frequently used entries"""
        with self._lock:
            self._cleanup_expired()
            
            # Sort entries by frequency (ascending)
            sorted_entries = sorted(
                [(freq, key) for key, freq in self._key_frequencies.items() if key in self._entries]
            )
            
            least_frequent = []
            for freq, key in sorted_entries[:count]:
                entry = self._entries[key]
                least_frequent.append({
                    'key': key,
                    'frequency': freq,
                    'age': entry.age,
                    'size': entry.size,
                    'created_at': entry.created_at,
                    'last_accessed': entry.accessed_at
                })
            
            return least_frequent
    
    def get_most_frequent_entries(self, count: int = 10) -> List[dict]:
        """Get information about the most frequently used entries"""
        with self._lock:
            self._cleanup_expired()
            
            # Sort entries by frequency (descending)
            sorted_entries = sorted(
                [(freq, key) for key, freq in self._key_frequencies.items() if key in self._entries],
                reverse=True
            )
            
            most_frequent = []
            for freq, key in sorted_entries[:count]:
                entry = self._entries[key]
                most_frequent.append({
                    'key': key,
                    'frequency': freq,
                    'age': entry.age,
                    'size': entry.size,
                    'created_at': entry.created_at,
                    'last_accessed': entry.accessed_at
                })
            
            return most_frequent
    
    def get_frequency_stats(self) -> dict:
        """Get comprehensive frequency statistics"""
        with self._lock:
            self._cleanup_expired()
            
            if not self._key_frequencies:
                return {
                    'total_entries': 0,
                    'min_frequency': 0,
                    'max_frequency': 0,
                    'avg_frequency': 0,
                    'median_frequency': 0,
                    'frequency_distribution': {}
                }
            
            frequencies = list(self._key_frequencies.values())
            frequencies.sort()
            
            total_entries = len(frequencies)
            min_freq = min(frequencies)
            max_freq = max(frequencies)
            avg_freq = sum(frequencies) / total_entries
            
            # Calculate median
            if total_entries % 2 == 0:
                median_freq = (frequencies[total_entries // 2 - 1] + frequencies[total_entries // 2]) / 2
            else:
                median_freq = frequencies[total_entries // 2]
            
            return {
                'total_entries': total_entries,
                'min_frequency': min_freq,
                'max_frequency': max_freq,
                'avg_frequency': avg_freq,
                'median_frequency': median_freq,
                'frequency_distribution': dict(self._frequency_distribution)
            }
    
    def get_key_frequency(self, key: str) -> Optional[int]:
        """Get the current frequency of a specific key"""
        with self._lock:
            return self._key_frequencies.get(key)
    
    def get_access_pattern_analysis(self, time_window_seconds: int = 3600) -> dict:
        """Analyze access patterns over a time window"""
        with self._lock:
            self._cleanup_expired()
            current_time = time.time()
            window_start = current_time - time_window_seconds
            
            # Analyze entries accessed within the time window
            recent_accesses = 0
            hot_entries = []  # High frequency entries accessed recently
            cold_entries = []  # Low frequency entries not accessed recently
            
            for key, freq in self._key_frequencies.items():
                if key in self._entries:
                    entry = self._entries[key]
                    recently_accessed = entry.accessed_at >= window_start
                    
                    if recently_accessed:
                        recent_accesses += 1
                        if freq >= 5:  # Consider high frequency
                            hot_entries.append({
                                'key': key,
                                'frequency': freq,
                                'last_accessed': entry.accessed_at
                            })
                    else:
                        if freq <= 2:  # Consider low frequency
                            cold_entries.append({
                                'key': key,
                                'frequency': freq,
                                'last_accessed': entry.accessed_at,
                                'age': entry.age
                            })
            
            return {
                'time_window_hours': time_window_seconds / 3600,
                'total_entries': len(self._entries),
                'recent_accesses': recent_accesses,
                'hot_entries_count': len(hot_entries),
                'cold_entries_count': len(cold_entries),
                'hot_entries': hot_entries[:10],  # Top 10
                'cold_entries': cold_entries[:10],  # Top 10
                'access_rate': recent_accesses / (time_window_seconds / 3600)  # per hour
            }
    
    def predict_eviction_candidates(self, count: int = 10) -> List[dict]:
        """Predict which entries are most likely to be evicted"""
        with self._lock:
            self._cleanup_expired()
            
            candidates = []
            
            # Get entries sorted by frequency (ascending) and age (descending for tie-breaking)
            entries_with_priority = []
            for key, freq in self._key_frequencies.items():
                if key in self._entries:
                    entry = self._entries[key]
                    # Priority: lower frequency = higher eviction probability
                    # For same frequency, older entries are more likely to be evicted
                    priority = (freq, -entry.created_at)
                    entries_with_priority.append((priority, key, freq, entry))
            
            # Sort by priority (lowest frequency first, then oldest)
            entries_with_priority.sort()
            
            for i, (priority, key, freq, entry) in enumerate(entries_with_priority[:count]):
                candidates.append({
                    'key': key,
                    'eviction_rank': i + 1,
                    'frequency': freq,
                    'age': entry.age,
                    'size': entry.size,
                    'last_accessed': entry.accessed_at,
                    'created_at': entry.created_at,
                    'eviction_probability': 1.0 - (freq / max(self._key_frequencies.values(), default=1))
                })
            
            return candidates
    
    def optimize_frequency_tracking(self) -> dict:
        """Optimize frequency tracking by cleaning up stale entries"""
        with self._lock:
            initial_heap_size = len(self._frequency_heap)
            initial_freq_size = len(self._key_frequencies)
            
            # Clean up frequency tracking for non-existent entries
            stale_keys = [key for key in self._key_frequencies.keys() if key not in self._entries]
            
            for key in stale_keys:
                freq = self._key_frequencies[key]
                self._frequency_distribution[freq] -= 1
                if self._frequency_distribution[freq] <= 0:
                    del self._frequency_distribution[freq]
                del self._key_frequencies[key]
            
            # Rebuild heap to remove stale entries
            self._rebuild_frequency_heap()
            
            final_heap_size = len(self._frequency_heap)
            final_freq_size = len(self._key_frequencies)
            
            return {
                'initial_heap_size': initial_heap_size,
                'final_heap_size': final_heap_size,
                'initial_frequency_tracking': initial_freq_size,
                'final_frequency_tracking': final_freq_size,
                'stale_entries_removed': len(stale_keys),
                'heap_rebuilt': True
            }
    
    def get_heap_integrity(self) -> dict:
        """Check the integrity of the frequency heap"""
        with self._lock:
            # Count valid vs stale entries in heap
            valid_entries = 0
            stale_entries = 0
            
            for freq, timestamp, key in self._frequency_heap:
                if (key in self._entries and 
                    key in self._key_frequencies and 
                    self._key_frequencies[key] == freq):
                    valid_entries += 1
                else:
                    stale_entries += 1
            
            total_heap_entries = len(self._frequency_heap)
            integrity_ratio = valid_entries / total_heap_entries if total_heap_entries > 0 else 1.0
            
            return {
                'total_heap_entries': total_heap_entries,
                'valid_entries': valid_entries,
                'stale_entries': stale_entries,
                'integrity_ratio': integrity_ratio,
                'needs_cleanup': integrity_ratio < 0.7,  # Suggest cleanup if < 70% valid
                'frequency_tracking_count': len(self._key_frequencies),
                'cache_entries_count': len(self._entries)
            }
    
    def reset_frequencies(self, keys: Optional[List[str]] = None) -> dict:
        """Reset frequencies for specified keys or all keys"""
        with self._lock:
            if keys is None:
                keys = list(self._key_frequencies.keys())
            
            reset_count = 0
            for key in keys:
                if key in self._key_frequencies and key in self._entries:
                    old_freq = self._key_frequencies[key]
                    
                    # Update distribution
                    self._frequency_distribution[old_freq] -= 1
                    if self._frequency_distribution[old_freq] <= 0:
                        del self._frequency_distribution[old_freq]
                    
                    # Reset to 1
                    self._key_frequencies[key] = 1
                    self._frequency_distribution[1] += 1
                    
                    reset_count += 1
            
            # Rebuild heap after frequency reset
            self._rebuild_frequency_heap()
            
            return {
                'keys_reset': reset_count,
                'total_keys': len(keys),
                'heap_rebuilt': True
            }