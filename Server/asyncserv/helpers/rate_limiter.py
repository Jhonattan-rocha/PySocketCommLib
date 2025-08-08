"""Rate limiting implementation using token bucket algorithm."""

import asyncio
import time
from typing import Optional


class AsyncTokenBucket:
    """Async implementation of token bucket algorithm for rate limiting.
    
    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit over time.
    
    Args:
        capacity: Maximum number of tokens the bucket can hold
        refill_rate: Rate at which tokens are added (tokens per second)
        initial_tokens: Initial number of tokens (defaults to capacity)
    """
    
    def __init__(self, capacity: int, refill_rate: float, initial_tokens: Optional[int] = None):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be positive")
            
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were successfully consumed, False otherwise
        """
        if tokens <= 0:
            raise ValueError("Tokens to consume must be positive")
            
        async with self._lock:
            await self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed > 0:
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
    
    async def get_available_tokens(self) -> float:
        """Get the current number of available tokens.
        
        Returns:
            Current number of tokens in the bucket
        """
        async with self._lock:
            await self._refill()
            return self.tokens
    
    async def wait_for_tokens(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Wait until enough tokens are available.
        
        Args:
            tokens: Number of tokens needed
            timeout: Maximum time to wait (None for no timeout)
            
        Returns:
            True if tokens became available, False if timeout occurred
        """
        if tokens <= 0:
            raise ValueError("Tokens must be positive")
            
        start_time = time.time()
        
        while True:
            if await self.consume(tokens):
                return True
                
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
                
            # Calculate how long to wait for next refill
            async with self._lock:
                await self._refill()
                tokens_needed = tokens - self.tokens
                if tokens_needed <= 0:
                    continue
                    
                wait_time = min(tokens_needed / self.refill_rate, 0.1)
                
            await asyncio.sleep(wait_time)
    
    def reset(self, tokens: Optional[int] = None):
        """Reset the bucket to initial state.
        
        Args:
            tokens: Number of tokens to set (defaults to capacity)
        """
        self.tokens = tokens if tokens is not None else self.capacity
        self.last_refill = time.time()
    
    @property
    def is_full(self) -> bool:
        """Check if the bucket is at full capacity."""
        return self.tokens >= self.capacity
    
    @property
    def is_empty(self) -> bool:
        """Check if the bucket has no tokens."""
        return self.tokens <= 0
    
    def __repr__(self) -> str:
        return f"AsyncTokenBucket(capacity={self.capacity}, refill_rate={self.refill_rate}, tokens={self.tokens:.2f})"


class RateLimiter:
    """Rate limiter that manages multiple token buckets for different clients."""
    
    def __init__(self, default_capacity: int = 10, default_refill_rate: float = 1.0):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.buckets: dict[str, AsyncTokenBucket] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    async def consume(self, client_id: str, tokens: int = 1) -> bool:
        """Consume tokens for a specific client.
        
        Args:
            client_id: Unique identifier for the client
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if rate limited
        """
        bucket = self._get_or_create_bucket(client_id)
        return await bucket.consume(tokens)
    
    async def wait_for_tokens(self, client_id: str, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Wait for tokens to become available for a client.
        
        Args:
            client_id: Unique identifier for the client
            tokens: Number of tokens needed
            timeout: Maximum time to wait
            
        Returns:
            True if tokens became available, False if timeout
        """
        bucket = self._get_or_create_bucket(client_id)
        return await bucket.wait_for_tokens(tokens, timeout)
    
    def _get_or_create_bucket(self, client_id: str) -> AsyncTokenBucket:
        """Get existing bucket or create new one for client."""
        if client_id not in self.buckets:
            self.buckets[client_id] = AsyncTokenBucket(
                capacity=self.default_capacity,
                refill_rate=self.default_refill_rate
            )
        
        # Periodic cleanup of old buckets
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_buckets()
        
        return self.buckets[client_id]
    
    def _cleanup_old_buckets(self):
        """Remove buckets that haven't been used recently."""
        current_time = time.time()
        to_remove = []
        
        for client_id, bucket in self.buckets.items():
            # Remove buckets that haven't been refilled in the last hour
            if current_time - bucket.last_refill > 3600:
                to_remove.append(client_id)
        
        for client_id in to_remove:
            del self.buckets[client_id]
        
        self._last_cleanup = current_time
    
    def remove_client(self, client_id: str):
        """Remove rate limiting for a specific client."""
        self.buckets.pop(client_id, None)
    
    def reset_client(self, client_id: str):
        """Reset rate limiting for a specific client."""
        if client_id in self.buckets:
            self.buckets[client_id].reset()
    
    def get_client_status(self, client_id: str) -> dict:
        """Get rate limiting status for a client."""
        if client_id not in self.buckets:
            return {
                "tokens": self.default_capacity,
                "capacity": self.default_capacity,
                "refill_rate": self.default_refill_rate
            }
        
        bucket = self.buckets[client_id]
        return {
            "tokens": bucket.tokens,
            "capacity": bucket.capacity,
            "refill_rate": bucket.refill_rate
        }