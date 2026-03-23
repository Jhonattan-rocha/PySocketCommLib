import re
import threading
from typing import Any, Callable
from ..Abstracts.AsyncExecutorMixin import AsyncExecutorMixin


class Events(AsyncExecutorMixin):
    """
    Sistema de eventos simples baseado em flags embutidas na mensagem.

    Formato de evento na mensagem: !{flag}:{arg1,arg2}!
    Exemplo: b"!{user_connected}:{user123,admin}!"

    AVISO: O scan de eventos é ativado por padrão apenas quando handlers
    estão registrados. Os eventos são executados em threads separadas.
    Certifique-se de que os dados que chegam ao scan() são confiáveis,
    pois qualquer payload com o padrão acima dispara o callback registrado.
    """

    # Padrão compilado uma vez, compartilhado entre instâncias
    _EVENT_PATTERN = re.compile(r'\!\{([^}]+)\}:\{([^}]*)\}\!', re.I)

    def __init__(self) -> None:
        self.__events: dict[str, Callable] = {}
        self.__lock = threading.Lock()

    def scan(self, data: bytes) -> None:
        """
        Escaneia os dados em busca de eventos embutidos e os dispara.

        Só processa se houver handlers registrados.
        Ignores silenciosamente flags sem handler registrado.
        """
        if not self.__events:
            return

        try:
            texto = data.decode('utf-8', errors='replace')
        except Exception:
            return

        events_found = self._EVENT_PATTERN.findall(texto)

        for event in events_found:
            flag = str(event[0]).strip()
            args_raw = str(event[1])
            args = [a.strip() for a in args_raw.split(",") if a.strip()] if args_raw else []

            with self.__lock:
                callback = self.__events.get(flag)

            if callback:
                threading.Thread(
                    target=callback,
                    args=tuple(args),
                    daemon=True
                ).start()

    def emit(self, flag: str, *args) -> None:
        """
        Dispara diretamente o callback registrado para um flag, sem parsing de bytes.

        Útil em contextos HTTP onde não há payload com o padrão de evento embutido.
        O callback é executado em uma thread daemon (fire-and-forget).
        """
        with self.__lock:
            callback = self.__events.get(flag)
        if callback:
            threading.Thread(target=callback, args=args, daemon=True).start()

    def size(self) -> int:
        return len(self.__events)

    def on(self, flag: str, call: Callable[..., Any]) -> None:
        """Registra um callback para um evento."""
        with self.__lock:
            self.__events[flag] = call

    def off(self, flag: str) -> None:
        """Remove o callback de um evento."""
        with self.__lock:
            self.__events.pop(flag, None)

