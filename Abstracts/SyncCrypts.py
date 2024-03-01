from abc import ABC, abstractclassmethod
from Options.Ops import SyncCrypt_ops

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
    