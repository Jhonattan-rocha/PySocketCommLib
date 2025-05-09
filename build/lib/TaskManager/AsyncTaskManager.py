from Abstracts.AsyncTask import AsyncTask 
import asyncio

class AsyncTaskManager:
    def __init__(self):
        self.__tasks: list[type[AsyncTask]] = []
        self.results = []

    async def register_task(self, task: AsyncTask) -> None:
        self.__tasks.append(task)

    async def run_all_tasks(self) -> None:
        futures = [asyncio.create_task(task.start()) for task in self.__tasks]
        for completed_task in asyncio.as_completed(futures):
            result = await completed_task
            self.results.append(result)

    async def stop_all_tasks(self) -> None:
        futures = [asyncio.create_task(task.stop()) for task in self.__tasks]
        for completed_task in asyncio.as_completed(futures):
            await completed_task
    
    async def get_task(self, uuid: str) -> AsyncTask | None:
        for task in self.__tasks:
            if await task.task_id() == uuid:
                return task
        return None
    
    async def stop_task(self, uuid: str) -> None:
        task = await self.get_task(uuid)
        await task.stop()
    