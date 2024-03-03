from abc import ABC, abstractclassmethod
from typing import Any, Callable
from Options.Ops import SyncCrypt_ops
import asyncio

class SyncCrypts(ABC):    
    @abstractclassmethod
    def __init__(self, Options: SyncCrypt_ops) -> None:
        pass
    @abstractclassmethod
    def encrypt_message(self, message: bytes) -> bytes:
        pass
    @abstractclassmethod
    def decrypt_message(self, encrypted_blocks: bytes) -> bytes:
        pass
    @abstractclassmethod
    def generate_key(self, size: int) -> None:
        pass
    @abstractclassmethod
    def get_key(self) -> bytes:
        pass
    @abstractclassmethod
    def set_key(self, key: bytes) -> None:
        pass
    # --async
    @abstractclassmethod
    async def async_executor(self, Call: Callable[..., Any], *args):
        pass