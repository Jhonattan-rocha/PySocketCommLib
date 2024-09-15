from abc import ABC, abstractmethod
from typing import Any, Callable
from Options.Ops import AsyncCrypt_ops


class AsyncCrypts(ABC):
    @abstractmethod
    def __init__(self, Options: AsyncCrypt_ops) -> None:
        pass

    @abstractmethod
    def load_public_key(self, public_key_bytes: bytes) -> object:
        pass

    @abstractmethod
    def public_key_to_bytes(self) -> bytes:
        pass

    @abstractmethod
    def generate_key_pair(self) -> None:
        pass

    @abstractmethod
    def encrypt_with_public_key(self, data: bytes, public_key=None) -> bytes:
        pass

    @abstractmethod
    def decrypt_with_private_key(self, data: bytes, private_key=None) -> bytes:
        pass

    #--async
    @abstractmethod
    async def async_executor(self, Call: Callable[..., Any], *args):
        pass
