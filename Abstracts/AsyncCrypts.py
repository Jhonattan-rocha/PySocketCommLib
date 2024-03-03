from abc import ABC, abstractclassmethod
from typing import Any, Callable
from Options.Ops import AsyncCrypt_ops

class AsyncCrypts(ABC):
    @abstractclassmethod
    def __init__(self, Options: AsyncCrypt_ops) -> None:
        pass
    @abstractclassmethod
    def load_public_key(self, public_key_bytes: bytes) -> object:
        pass
    @abstractclassmethod
    def public_key_to_bytes(self) -> bytes:
        pass
    @abstractclassmethod
    def generate_key_pair(self) -> None:
        pass
    @abstractclassmethod
    def encrypt_with_public_key(self, data:bytes, public_key=None) -> bytes:
        pass
    @abstractclassmethod
    def decrypt_with_private_key(self, data:bytes, private_key=None) -> bytes:
        pass
    #--async
    @abstractclassmethod
    async def async_execute(self, Call: Callable[..., Any], *args):
        pass
