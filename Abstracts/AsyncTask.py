import uuid
from typing import Callable, Any
from abc import ABC


class AsyncTask(ABC):
    def __init__(self, call: Callable[..., Any], *args):
        self._uuid = uuid.uuid4()
        self._running = True
        self._task = [call, [*args]]

    @classmethod
    async def start(cls) -> None:
        pass

    @classmethod
    async def stop(cls) -> None:
        pass

    async def task_id(self) -> str:
        return str(self._uuid)
