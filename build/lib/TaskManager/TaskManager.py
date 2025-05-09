from Abstracts.ThreadTask import ThreadTask
import queue


class TaskManager:
    def __init__(self):
        self.__tasks: list[ThreadTask] = []
        self.results: queue.Queue = queue.Queue()

    def register_task(self, task: ThreadTask):
        self.__tasks.append(task)

    def run_all_tasks(self) -> None:
        for task in self.__tasks:
            task.set_result_queue(self.results)
            task.start()

    def stop_all_tasks(self) -> None:
        for task in self.__tasks:
            task.stop()

    def get_task(self, uuid: str) -> ThreadTask | None:
        for task in self.__tasks:
            if task.task_id() == uuid:
                return task
        return None

    def stop_task(self, uuid: str) -> None:
        task = self.get_task(uuid)
        task.stop()
