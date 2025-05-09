import time
from typing import Any

class MemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def set(self, key: str, value: Any, ttl: int = 300):
        expires_at = time.time() + ttl
        self._store[key] = (value, expires_at)

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def clear_prefix(self, prefix: str):
        keys_to_delete = [key for key in self._store if key.startswith(prefix)]
        for key in keys_to_delete:
            del self._store[key]

    def clear_all(self):
        self._store.clear()
