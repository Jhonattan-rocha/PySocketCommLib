import asyncio
from typing import Any, Callable


class AsyncExecutorMixin:
    """
    Mixin que fornece execução assíncrona de funções síncronas bloqueantes.

    Usa o executor padrão do asyncio (ThreadPoolExecutor compartilhado),
    evitando a criação de um novo pool por chamada.
    """

    async def async_executor(self, Call: Callable[..., Any], *args) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, Call, *args)
