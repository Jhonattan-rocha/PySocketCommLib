from abc import ABC, abstractclassmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from typing import Protocol
import asyncio
import random
import uuid
import hashlib
import string

class Client(Protocol):
    pass

class Auth(ABC):
    
    def __init__(self, token: str) -> None:
        self.token = token
    
    @abstractclassmethod
    def send_token(self, client: Client) -> str:
        pass

    @abstractclassmethod
    def get_token(self, client: Client) -> str:
        pass
    
    @abstractclassmethod
    def set_token(self, client: Client) -> str:
        pass
    
    @abstractclassmethod
    def validate_token(self, client: Client) -> bool:
        pass
    
    @abstractclassmethod
    def generate_token(self) -> str:
        pass
    
    def hash_str(self, st: str):
        st = hashlib.sha512(st).hexdigest()       
        return st
    
    def generate_random_str(self, lng: int) -> str:
        chars = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.digits + string.hexdigits + string.printable
        return ''.join([random.choice(chars) for _ in range(lng)])
    
    def generate_unique_id(self) -> int:
        return uuid.uuid4().int
    
    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res
    