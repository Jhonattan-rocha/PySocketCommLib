import threading
import uuid
from typing import Callable, Any
from abc import ABC, abstractmethod
import queue

class ThreadTask(ABC, threading.Thread):
    def __init__(self, call: Callable[..., Any], *args):
        super().__init__()
        self._uuid = uuid.uuid4()
        self._running = threading.Event()
        self._task = [call, [*args]]
        self.result_queue: queue.Queue = None

    def set_result_queue(self, result_queue: queue.Queue) -> None:
        self.result_queue = result_queue

    @abstractmethod
    def run(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    def task_id(self) -> str:
        return str(self._uuid)
