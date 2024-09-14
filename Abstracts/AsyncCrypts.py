from abc import ABC
from typing import Any, Callable
from Options.Ops import AsyncCrypt_ops


class AsyncCrypts(ABC):
    @classmethod
    def __init__(cls, Options: AsyncCrypt_ops) -> None:
        pass

    @classmethod
    def load_public_key(cls, public_key_bytes: bytes) -> object:
        pass

    @classmethod
    def public_key_to_bytes(cls) -> bytes:
        pass

    @classmethod
    def generate_key_pair(cls) -> None:
        pass

    @classmethod
    def encrypt_with_public_key(cls, data: bytes, public_key=None) -> bytes:
        pass

    @classmethod
    def decrypt_with_private_key(cls, data: bytes, private_key=None) -> bytes:
        pass

    #--async
    @classmethod
    async def async_executor(cls, Call: Callable[..., Any], *args):
        pass
