"""Cache Decorators - Easy-to-use caching decorators

Provides decorators for automatic caching of function results with support for
various cache strategies and configurations.
"""

import time
import asyncio
import functools
import hashlib
import inspect
from typing import Any, Optional, Callable, Union, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from .cache_manager import CacheManager
from .config import CacheConfig, CacheStrategy
from ..log_utils import StructuredLogger


# Global cache manager instance
_default_cache_manager: Optional[CacheManager] = None
_logger = StructuredLogger()


def set_default_cache_manager(cache_manager: CacheManager):
    """Set the default cache manager for decorators"""
    global _default_cache_manager
    _default_cache_manager = cache_manager


def get_default_cache_manager() -> CacheManager:
    """Get or create the default cache manager"""
    global _default_cache_manager
    if _default_cache_manager is None:
        _default_cache_manager = CacheManager()
    return _default_cache_manager


def _generate_cache_key(func: Callable, args: tuple, kwargs: dict, 
                       key_prefix: Optional[str] = None,
                       include_func_name: bool = True) -> str:
    """Generate a cache key from function and arguments"""
    key_parts = []
    
    # Add custom prefix if provided
    if key_prefix:
        key_parts.append(key_prefix)
    
    # Add function name and module
    if include_func_name:
        func_name = f"{func.__module__}.{func.__qualname__}"
        key_parts.append(func_name)
    
    # Add arguments
    if args:
        args_str = str(args)
        key_parts.append(f"args:{args_str}")
    
    if kwargs:
        # Sort kwargs for consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = str(sorted_kwargs)
        key_parts.append(f"kwargs:{kwargs_str}")
    
    # Create final key
    key_string = "|".join(key_parts)
    
    # Hash if too long
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"hashed:{key_hash}"
    
    return key_string


def _should_cache_result(result: Any, cache_none: bool = False, 
                        cache_exceptions: bool = False) -> bool:
    """Determine if a result should be cached"""
    if isinstance(result, Exception):
        return cache_exceptions
    
    if result is None:
        return cache_none
    
    return True


def cache(ttl: Optional[float] = None,
          key_prefix: Optional[str] = None,
          cache_manager: Optional[CacheManager] = None,
          cache_none: bool = False,
          cache_exceptions: bool = False,
          ignore_args: Optional[List[str]] = None,
          condition: Optional[Callable[..., bool]] = None,
          serializer: Optional[str] = None,
          on_hit: Optional[Callable[[str, Any], None]] = None,
          on_miss: Optional[Callable[[str], None]] = None,
          on_error: Optional[Callable[[str, Exception], None]] = None):
    """Cache decorator for synchronous functions
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Custom prefix for cache keys
        cache_manager: Custom cache manager instance
        cache_none: Whether to cache None results
        cache_exceptions: Whether to cache exceptions
        ignore_args: List of argument names to ignore in key generation
        condition: Function to determine if result should be cached
        serializer: Serializer to use (json, pickle, msgpack)
        on_hit: Callback for cache hits
        on_miss: Callback for cache misses
        on_error: Callback for cache errors
    """
    
    def decorator(func: Callable) -> Callable:
        # Get function signature for argument handling
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager
            cm = cache_manager or get_default_cache_manager()
            
            # Filter arguments if needed
            filtered_kwargs = kwargs.copy()
            if ignore_args:
                for arg_name in ignore_args:
                    filtered_kwargs.pop(arg_name, None)
            
            # Generate cache key
            cache_key = _generate_cache_key(
                func, args, filtered_kwargs, key_prefix
            )
            
            try:
                # Try to get from cache
                cached_result = cm.get(cache_key)
                
                if cached_result is not None:
                    # Cache hit
                    if on_hit:
                        on_hit(cache_key, cached_result)
                    
                    _logger.debug("Cache hit", extra={
                        'function': func.__name__,
                        'cache_key': cache_key
                    })
                    
                    return cached_result
                
                # Cache miss - execute function
                if on_miss:
                    on_miss(cache_key)
                
                _logger.debug("Cache miss", extra={
                    'function': func.__name__,
                    'cache_key': cache_key
                })
                
                result = func(*args, **kwargs)
                
                # Check if we should cache this result
                should_cache = _should_cache_result(result, cache_none, cache_exceptions)
                
                # Apply condition if provided
                if condition and not condition(*args, **kwargs):
                    should_cache = False
                
                if should_cache:
                    # Store in cache
                    cm.set(cache_key, result, ttl)
                    
                    _logger.debug("Result cached", extra={
                        'function': func.__name__,
                        'cache_key': cache_key,
                        'ttl': ttl
                    })
                
                return result
                
            except Exception as e:
                if on_error:
                    on_error(cache_key, e)
                
                _logger.error("Cache operation error", extra={
                    'function': func.__name__,
                    'cache_key': cache_key,
                    'error': str(e)
                })
                
                # Execute function anyway
                return func(*args, **kwargs)
        
        # Add cache management methods to the wrapper
        wrapper._cache_manager = cache_manager or get_default_cache_manager()
        wrapper._cache_key_prefix = key_prefix
        
        def invalidate(*args, **kwargs):
            """Invalidate cache for specific arguments"""
            cm = cache_manager or get_default_cache_manager()
            filtered_kwargs = kwargs.copy()
            if ignore_args:
                for arg_name in ignore_args:
                    filtered_kwargs.pop(arg_name, None)
            
            cache_key = _generate_cache_key(
                func, args, filtered_kwargs, key_prefix
            )
            return cm.delete(cache_key)
        
        def invalidate_all():
            """Invalidate all cache entries for this function"""
            cm = cache_manager or get_default_cache_manager()
            func_prefix = f"{func.__module__}.{func.__qualname__}"
            
            # Get all keys and filter by function
            all_keys = cm.get_keys()
            function_keys = [key for key in all_keys if func_prefix in key]
            
            if function_keys:
                return cm.delete_many(function_keys)
            return {}
        
        def get_cache_stats():
            """Get cache statistics for this function"""
            cm = cache_manager or get_default_cache_manager()
            return cm.get_stats()
        
        # Attach methods to wrapper
        wrapper.invalidate = invalidate
        wrapper.invalidate_all = invalidate_all
        wrapper.get_cache_stats = get_cache_stats
        
        return wrapper
    
    return decorator


def cache_async(ttl: Optional[float] = None,
                key_prefix: Optional[str] = None,
                cache_manager: Optional[CacheManager] = None,
                cache_none: bool = False,
                cache_exceptions: bool = False,
                ignore_args: Optional[List[str]] = None,
                condition: Optional[Callable[..., bool]] = None,
                serializer: Optional[str] = None,
                on_hit: Optional[Callable[[str, Any], None]] = None,
                on_miss: Optional[Callable[[str], None]] = None,
                on_error: Optional[Callable[[str, Exception], None]] = None):
    """Cache decorator for asynchronous functions"""
    
    def decorator(func: Callable) -> Callable:
        # Get function signature for argument handling
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache manager
            cm = cache_manager or get_default_cache_manager()
            
            # Filter arguments if needed
            filtered_kwargs = kwargs.copy()
            if ignore_args:
                for arg_name in ignore_args:
                    filtered_kwargs.pop(arg_name, None)
            
            # Generate cache key
            cache_key = _generate_cache_key(
                func, args, filtered_kwargs, key_prefix
            )
            
            try:
                # Try to get from cache
                cached_result = await cm.get_async(cache_key)
                
                if cached_result is not None:
                    # Cache hit
                    if on_hit:
                        if asyncio.iscoroutinefunction(on_hit):
                            await on_hit(cache_key, cached_result)
                        else:
                            on_hit(cache_key, cached_result)
                    
                    _logger.debug("Async cache hit", extra={
                        'function': func.__name__,
                        'cache_key': cache_key
                    })
                    
                    return cached_result
                
                # Cache miss - execute function
                if on_miss:
                    if asyncio.iscoroutinefunction(on_miss):
                        await on_miss(cache_key)
                    else:
                        on_miss(cache_key)
                
                _logger.debug("Async cache miss", extra={
                    'function': func.__name__,
                    'cache_key': cache_key
                })
                
                result = await func(*args, **kwargs)
                
                # Check if we should cache this result
                should_cache = _should_cache_result(result, cache_none, cache_exceptions)
                
                # Apply condition if provided
                if condition:
                    if asyncio.iscoroutinefunction(condition):
                        should_cache = should_cache and await condition(*args, **kwargs)
                    else:
                        should_cache = should_cache and condition(*args, **kwargs)
                
                if should_cache:
                    # Store in cache
                    await cm.set_async(cache_key, result, ttl)
                    
                    _logger.debug("Async result cached", extra={
                        'function': func.__name__,
                        'cache_key': cache_key,
                        'ttl': ttl
                    })
                
                return result
                
            except Exception as e:
                if on_error:
                    if asyncio.iscoroutinefunction(on_error):
                        await on_error(cache_key, e)
                    else:
                        on_error(cache_key, e)
                
                _logger.error("Async cache operation error", extra={
                    'function': func.__name__,
                    'cache_key': cache_key,
                    'error': str(e)
                })
                
                # Execute function anyway
                return await func(*args, **kwargs)
        
        # Add cache management methods to the wrapper
        wrapper._cache_manager = cache_manager or get_default_cache_manager()
        wrapper._cache_key_prefix = key_prefix
        
        async def invalidate(*args, **kwargs):
            """Invalidate cache for specific arguments"""
            cm = cache_manager or get_default_cache_manager()
            filtered_kwargs = kwargs.copy()
            if ignore_args:
                for arg_name in ignore_args:
                    filtered_kwargs.pop(arg_name, None)
            
            cache_key = _generate_cache_key(
                func, args, filtered_kwargs, key_prefix
            )
            return await cm.delete_async(cache_key)
        
        async def invalidate_all():
            """Invalidate all cache entries for this function"""
            cm = cache_manager or get_default_cache_manager()
            func_prefix = f"{func.__module__}.{func.__qualname__}"
            
            # Get all keys and filter by function
            all_keys = cm.get_keys()
            function_keys = [key for key in all_keys if func_prefix in key]
            
            if function_keys:
                results = {}
                for key in function_keys:
                    results[key] = await cm.delete_async(key)
                return results
            return {}
        
        def get_cache_stats():
            """Get cache statistics for this function"""
            cm = cache_manager or get_default_cache_manager()
            return cm.get_stats()
        
        # Attach methods to wrapper
        wrapper.invalidate = invalidate
        wrapper.invalidate_all = invalidate_all
        wrapper.get_cache_stats = get_cache_stats
        
        return wrapper
    
    return decorator


def memoize(maxsize: int = 128, ttl: Optional[float] = None):
    """Simple memoization decorator with LRU eviction"""
    return cache(
        ttl=ttl,
        cache_manager=CacheManager(CacheConfig(
            max_size=maxsize,
            strategy=CacheStrategy.LRU
        ))
    )


def timed_cache(seconds: float):
    """Cache with TTL-based expiration"""
    return cache(ttl=seconds)


def conditional_cache(condition: Callable[..., bool], ttl: Optional[float] = None):
    """Cache only when condition is met"""
    return cache(ttl=ttl, condition=condition)


def cache_result(key: str, ttl: Optional[float] = None, 
                cache_manager: Optional[CacheManager] = None):
    """Cache decorator with explicit key"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cm = cache_manager or get_default_cache_manager()
            
            # Try to get from cache
            cached_result = cm.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cm.set(key, result, ttl)
            return result
        
        def invalidate():
            """Invalidate this specific cache entry"""
            cm = cache_manager or get_default_cache_manager()
            return cm.delete(key)
        
        wrapper.invalidate = invalidate
        return wrapper
    
    return decorator


def cache_property(ttl: Optional[float] = None, 
                  cache_manager: Optional[CacheManager] = None):
    """Cache decorator for class properties"""
    def decorator(func: Callable) -> property:
        attr_name = f"_cached_{func.__name__}"
        
        def getter(self):
            # Check if we have a cached value
            if hasattr(self, attr_name):
                cached_value, cached_time = getattr(self, attr_name)
                
                # Check TTL
                if ttl is None or (time.time() - cached_time) < ttl:
                    return cached_value
            
            # Compute and cache the value
            value = func(self)
            setattr(self, attr_name, (value, time.time()))
            return value
        
        def deleter(self):
            if hasattr(self, attr_name):
                delattr(self, attr_name)
        
        return property(getter, None, deleter)
    
    return decorator


class CacheContext:
    """Context manager for temporary cache configuration"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.original_manager = None
    
    def __enter__(self):
        global _default_cache_manager
        self.original_manager = _default_cache_manager
        _default_cache_manager = self.cache_manager
        return self.cache_manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        global _default_cache_manager
        _default_cache_manager = self.original_manager


def with_cache_manager(cache_manager: CacheManager):
    """Context manager for using a specific cache manager"""
    return CacheContext(cache_manager)


# Utility functions for cache management
def clear_all_caches(cache_manager: Optional[CacheManager] = None):
    """Clear all caches"""
    cm = cache_manager or get_default_cache_manager()
    return cm.clear()


def get_cache_info(cache_manager: Optional[CacheManager] = None) -> Dict[str, Any]:
    """Get comprehensive cache information"""
    cm = cache_manager or get_default_cache_manager()
    return cm.get_stats()


def warm_cache_from_dict(data: Dict[str, Any], ttl: Optional[float] = None,
                        cache_manager: Optional[CacheManager] = None) -> Dict[str, bool]:
    """Warm cache with dictionary data"""
    cm = cache_manager or get_default_cache_manager()
    return cm.set_many(data, ttl)


# Performance monitoring decorators
def monitor_cache_performance(func: Callable) -> Callable:
    """Decorator to monitor cache performance"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            _logger.info("Cache operation completed", extra={
                'function': func.__name__,
                'duration': duration,
                'success': success
            })
    
    return wrapper


# Batch cache operations
def cache_batch(keys: List[str], ttl: Optional[float] = None,
               cache_manager: Optional[CacheManager] = None):
    """Decorator for batch caching operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cm = cache_manager or get_default_cache_manager()
            
            # Try to get all keys from cache
            cached_results = cm.get_many(keys)
            missing_keys = [key for key in keys if key not in cached_results]
            
            if not missing_keys:
                # All keys found in cache
                return [cached_results[key] for key in keys]
            
            # Execute function for missing keys
            results = func(missing_keys, *args, **kwargs)
            
            # Cache the new results
            if isinstance(results, dict):
                cm.set_many(results, ttl)
                # Return results in original key order
                return [cached_results.get(key) or results.get(key) for key in keys]
            else:
                # Assume results is a list corresponding to missing_keys
                new_cache_data = dict(zip(missing_keys, results))
                cm.set_many(new_cache_data, ttl)
                
                # Combine cached and new results
                final_results = []
                result_iter = iter(results)
                for key in keys:
                    if key in cached_results:
                        final_results.append(cached_results[key])
                    else:
                        final_results.append(next(result_iter))
                
                return final_results
        
        return wrapper
    
    return decorator