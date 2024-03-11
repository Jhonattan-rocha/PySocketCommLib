import threading
import uuid
from typing import Callable, Any

class Task(threading.Thread):
    def __init__(self, call: Callable[..., Any], *args):
        threading.Thread.__init__(self)
        self._uuid = uuid.uuid4()
        self._running = threading.Event()
        self._task = [call, [*args]]

    def run(self) -> None:
        while self.running.is_set():
           self.task[0](*self.task[1])

    def stop(self) -> None:
        self.running.clear()
    
    def task_id(self) -> str:
        return str(self._uuid)
  