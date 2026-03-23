"""Middleware de eventos: escaneia inbound e dispara callbacks registrados."""
import logging
from ..Abstracts.IOPipeline import IOMiddleware, AsyncIOMiddleware

logger = logging.getLogger(__name__)


class EventsMiddleware(IOMiddleware):
    """Middleware síncrono: dispara eventos embutidos nos dados recebidos."""

    def __init__(self, events) -> None:
        self.events = events

    def process_inbound(self, data: bytes, ctx=None) -> bytes:
        if self.events.size() > 0:
            self.events.scan(data)
        return data

    def process_outbound(self, data: bytes, ctx=None) -> bytes:
        return data


class AsyncEventsMiddleware(AsyncIOMiddleware):
    """Middleware assíncrono de eventos."""

    def __init__(self, events) -> None:
        self.events = events

    async def process_inbound(self, data: bytes, ctx=None) -> bytes:
        if await self.events.async_executor(self.events.size) > 0:
            await self.events.async_executor(self.events.scan, data)
        return data

    async def process_outbound(self, data: bytes, ctx=None) -> bytes:
        return data
