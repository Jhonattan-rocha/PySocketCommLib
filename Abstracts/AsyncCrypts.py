from abc import ABC, abstractclassmethod
from Options.Ops import AsyncCrypt_ops

class AsyncCrypts(ABC):
    @abstractclassmethod
    def __init__(self, Options: AsyncCrypt_ops) -> None:
        pass
    @abstractclassmethod
    def load_public_key(self, public_key_bytes: bytes) -> None:
        pass
    @abstractclassmethod
    def generate_key_pair(self) -> None:
        pass
    @abstractclassmethod
    def encrypt_with_public_key(self, data:bytes, public_key) -> bytes:
        pass
    @abstractclassmethod
    def decrypt_with_private_key(self, data:bytes, public_key) -> bytes:
        pass
    