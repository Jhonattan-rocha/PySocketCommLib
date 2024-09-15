import uuid
from typing import Callable, Any
from abc import ABC, abstractmethod


class AsyncTask(ABC):
    def __init__(self, call: Callable[..., Any], *args):
        self._uuid = uuid.uuid4()
        self._running = True
        self._task = [call, [*args]]

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    async def task_id(self) -> str:
        return str(self._uuid)
