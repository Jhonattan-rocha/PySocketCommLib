from TaskManager.Task import Task

class TaskManager:
    def __init__(self):
        self.__tasks: list[type[Task]] = []

    def register_task(self, task: Task):
        self.__tasks.append(task)

    def run_all_tasks(self):
        for task in self.__tasks:
            task.start()

    def stop_all_tasks(self):
        for task in self.__tasks:
            task.stop()
    
    def get_task(self, uuid: str) -> Task | None:
        for task in self.__tasks:
            if task.task_id() == uuid:
                return task
        return None
    
    def stop_task(self, uuid: str) -> None:
        task = self.get_task(uuid)
        task.stop()
    
