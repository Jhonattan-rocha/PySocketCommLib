import uuid
from typing import Callable, Any
from abc import ABC, abstractclassmethod

class AsyncTask(ABC):
    def __init__(self, call: Callable[..., Any], *args):
        self._uuid = uuid.uuid4()
        self._running = True
        self._task = [call, [*args]]

    @abstractclassmethod
    async def start(self) -> None:
        pass

    @abstractclassmethod
    async def stop(self) -> None:
        pass
    
    async def task_id(self) -> str:
        return str(self._uuid)
  