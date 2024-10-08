import random
import string
import asyncio
from typing import Any, Callable
from Abstracts.SyncCrypts import SyncCrypts
from Options import SyncCrypt_ops
from cryptography.fernet import Fernet
from concurrent.futures import ThreadPoolExecutor

class FernetCrypt(SyncCrypts):
    def __init__(self, Options: SyncCrypt_ops) -> None:
        self.__sync_key: bytes = Options.sync_key if Options.sync_key else Fernet.generate_key()
        try:
            self.sync_crypt = Fernet(self.__sync_key)
        except Exception as e:
            self.__sync_key = Fernet.generate_key()
            self.sync_crypt = Fernet(self.__sync_key)
            print(f"Devido ao erro: {e}, foi gerado uma nova chave")
        
    def encrypt_message(self, message: bytes):
        try:
            return self.sync_crypt.encrypt(message)
        except Exception as e:
            print(e)
            return b""

    def decrypt_message(self, encrypted_blocks: bytes):
        try:
            return self.sync_crypt.decrypt(encrypted_blocks)
        except Exception as e:
            print(e)
            return b""
        
    def generate_key(self, size: int) -> None:
        text = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.hexdigits
        key = "".join(random.choice(text) for _ in range(size))
        self.set_key(key.encode())
    
    def set_key(self, key: bytes) -> None:
        try:
            self.__sync_key = key
            self.sync_crypt = Fernet(self.__sync_key)
        except Exception as e:
            self.__sync_key = Fernet.generate_key()
            self.sync_crypt = Fernet(self.__sync_key)
    
    def get_key(self) -> bytes:
        return self.__sync_key

    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res