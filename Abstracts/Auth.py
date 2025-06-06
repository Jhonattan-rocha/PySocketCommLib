from abc import ABC, abstractmethod
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

    @abstractmethod
    def get_token(self, client: Client | None = None) -> str:
        pass

    @abstractmethod
    def set_token(self, client: Client | None = None, token: str = "") -> str:
        pass

    @abstractmethod
    def validate_token(self, client: Client | None = None) -> bool:
        pass

    @abstractmethod
    def generate_token(self) -> str:
        pass

    @staticmethod
    def hash_str(st: str):
        st = hashlib.sha512(st.encode()).hexdigest()
        return st

    @staticmethod
    def generate_random_str(lng: int) -> str:
        chars = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.digits + string.hexdigits + string.printable
        return ''.join([random.choice(chars) for _ in range(lng)])

    @staticmethod
    def generate_unique_id() -> int:
        return uuid.uuid4().int

    @staticmethod
    async def async_executor(Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res
