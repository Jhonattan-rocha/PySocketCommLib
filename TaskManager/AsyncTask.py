import uuid
from typing import Callable, Any

class AsyncTask():
    def __init__(self, call: Callable[..., Any], *args):
        self._uuid = uuid.uuid4()
        self._running = True
        self._task = [call, [*args]]

    async def start(self) -> None:
        while self.running.is_set():
           await self.task[0](*self.task[1])

    async def stop(self) -> None:
        self.running = False
    
    async def task_id(self) -> str:
        return str(self._uuid)
  