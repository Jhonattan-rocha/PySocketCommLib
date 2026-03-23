"""
ThreadConnectionTask — wrapper de ThreadConnectionContext para o TaskManager.

Permite que o TaskManager gerencie o ciclo de vida de cada conexão ativa:
  - task_id() → uuid do contexto
  - run()     → no-op (o servidor já gerencia o accept loop)
  - stop()    → desconecta o cliente de forma segura
"""
from ...Abstracts.ThreadTask import ThreadTask
from ...Abstracts.ConnectionContext import ThreadConnectionContext


class ThreadConnectionTask(ThreadTask):
    def __init__(self, ctx: ThreadConnectionContext) -> None:
        super().__init__(ctx.disconnect)
        self._ctx = ctx

    def run(self) -> None:
        # O accept loop do ThreadServer gerencia as conexões.
        pass

    def stop(self) -> None:
        self._running.clear()
        self._ctx.disconnect()

    def task_id(self) -> str:
        return self._ctx.uuid
