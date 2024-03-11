from TaskManager.AsyncTask import AsyncTask 
import asyncio

class AsyncTaskManager:
    def __init__(self):
        self.__tasks: list[type[AsyncTask]] = []
        self.results = []

    async def register_task(self, task: AsyncTask) -> None:
        self.__tasks.append(task)

    async def run_all_tasks(self) -> None:
        aux = []
        for task in self.__tasks:
            aux.append(asyncio.create_task(task.start()))
        
        self.results = await asyncio.gather(aux)

    async def stop_all_tasks(self) -> None:
        aux = []
        for task in self.__tasks:
            aux.append(asyncio.create_task(task.stop()))
        
        await asyncio.gather(aux)
    
    async def get_task(self, uuid: str) -> AsyncTask | None:
        for task in self.__tasks:
            if await task.task_id() == uuid:
                return task
        return None
    
    async def stop_task(self, uuid: str) -> None:
        task = await self.get_task(uuid)
        await task.stop()
    
