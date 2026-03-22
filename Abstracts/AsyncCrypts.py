from abc import ABC, abstractmethod
from ..Options import AsyncCrypt_ops
from .AsyncExecutorMixin import AsyncExecutorMixin


class AsyncCrypts(AsyncExecutorMixin, ABC):
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
