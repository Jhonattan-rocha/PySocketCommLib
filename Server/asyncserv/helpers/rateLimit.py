import time
import asyncio

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens por segundo
        self.capacity = capacity
        self.tokens = capacity
        self.last_check = time.monotonic()
        self.lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_check
            self.last_check = now

            # recarrega tokens
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
