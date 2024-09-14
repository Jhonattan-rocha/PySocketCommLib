from abc import ABC
from typing import Any, Callable
from Options.Ops import SyncCrypt_ops


class SyncCrypts(ABC):
    @classmethod
    def __init__(cls, Options: SyncCrypt_ops) -> None:
        pass

    @classmethod
    def encrypt_message(cls, message: bytes) -> bytes:
        pass

    @classmethod
    def decrypt_message(cls, encrypted_blocks: bytes) -> bytes:
        pass

    @classmethod
    def generate_key(cls, size: int) -> None:
        pass

    @classmethod
    def get_key(cls) -> bytes:
        pass

    @classmethod
    def set_key(cls, key: bytes) -> None:
        pass

    # --async
    @classmethod
    async def async_executor(cls, Call: Callable[..., Any], *args):
        pass
