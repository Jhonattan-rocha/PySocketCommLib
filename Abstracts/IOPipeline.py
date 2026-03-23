"""
IOPipeline — base para pipelines de transformação de dados I/O.

Cada middleware transforma dados em trânsito (inbound/outbound).
O pipeline aplica os middlewares em ordem para inbound e em ordem
inversa para outbound, seguindo o modelo "onion":

  Ordem de adição: [Codec, Crypt, Events]
    inbound  : Codec.decode → Crypt.decrypt → Events.scan
    outbound : Events(passthru) → Crypt.encrypt → Codec.encode
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, List


class IOMiddleware(ABC):
    """Middleware síncrono para I/O de socket."""

    @abstractmethod
    def process_inbound(self, data: bytes, ctx=None) -> bytes:
        """Transforma dados recebidos (ex: decode, decrypt)."""
        ...

    @abstractmethod
    def process_outbound(self, data: bytes, ctx=None) -> bytes:
        """Transforma dados a enviar (ex: encrypt, encode)."""
        ...


class AsyncIOMiddleware(ABC):
    """Middleware assíncrono para I/O de socket."""

    @abstractmethod
    async def process_inbound(self, data: bytes, ctx=None) -> bytes:
        ...

    @abstractmethod
    async def process_outbound(self, data: bytes, ctx=None) -> bytes:
        ...


class IOPipeline:
    """Pipeline síncrono: aplica middlewares em sequência."""

    def __init__(self) -> None:
        self._middlewares: List[IOMiddleware] = []

    def add(self, middleware: IOMiddleware) -> "IOPipeline":
        self._middlewares.append(middleware)
        return self

    def process_inbound(self, data: bytes, ctx=None) -> bytes:
        for mw in self._middlewares:
            data = mw.process_inbound(data, ctx)
        return data

    def process_outbound(self, data: bytes, ctx=None) -> bytes:
        for mw in reversed(self._middlewares):
            data = mw.process_outbound(data, ctx)
        return data


class AsyncIOPipeline:
    """Pipeline assíncrono: suporta middlewares síncronos e assíncronos."""

    def __init__(self) -> None:
        self._middlewares: List[Any] = []  # IOMiddleware | AsyncIOMiddleware

    def add(self, middleware: Any) -> "AsyncIOPipeline":
        self._middlewares.append(middleware)
        return self

    async def process_inbound(self, data: bytes, ctx=None) -> bytes:
        for mw in self._middlewares:
            result = mw.process_inbound(data, ctx)
            data = await result if asyncio.iscoroutine(result) else result
        return data

    async def process_outbound(self, data: bytes, ctx=None) -> bytes:
        for mw in reversed(self._middlewares):
            result = mw.process_outbound(data, ctx)
            data = await result if asyncio.iscoroutine(result) else result
        return data
