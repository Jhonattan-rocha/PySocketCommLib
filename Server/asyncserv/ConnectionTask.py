"""
AsyncConnectionTask — wrapper de AsyncConnectionContext para o AsyncTaskManager.

Permite que o TaskManager gerencie o ciclo de vida de cada conexão ativa:
  - task_id()  → uuid do contexto (consistente com ConnectionContext.uuid)
  - start()    → no-op (asyncio.start_server já gerencia a execução)
  - stop()     → desconecta o cliente de forma segura
"""
from ...Abstracts.AsyncTask import AsyncTask
from ...Abstracts.ConnectionContext import AsyncConnectionContext


class AsyncConnectionTask(AsyncTask):
    def __init__(self, ctx: AsyncConnectionContext) -> None:
        super().__init__(ctx.disconnect)
        self._ctx = ctx

    async def start(self) -> None:
        # asyncio.start_server já criou e executa a coroutine da conexão.
        pass

    async def stop(self) -> None:
        self._running = False
        await self._ctx.disconnect()

    async def task_id(self) -> str:
        return self._ctx.uuid
