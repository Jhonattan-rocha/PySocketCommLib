from abc import ABC, abstractmethod
from typing import Any, Callable
from Options import SyncCrypt_ops


class SyncCrypts(ABC):
    @abstractmethod
    def __init__(self, Options: SyncCrypt_ops) -> None:
        pass

    @abstractmethod
    def encrypt_message(self, message: bytes) -> bytes:
        pass

    @abstractmethod
    def decrypt_message(self, encrypted_blocks: bytes) -> bytes:
        pass

    @abstractmethod
    def generate_key(self, size: int) -> None:
        pass

    @abstractmethod
    def get_key(self) -> bytes:
        pass

    @abstractmethod
    def set_key(self, key: bytes) -> None:
        pass

    # --async
    @abstractmethod
    async def async_executor(self, Call: Callable[..., Any], *args):
        pass
