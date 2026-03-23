"""Middleware de criptografia: encrypt em outbound, decrypt em inbound."""
import logging
from ..Abstracts.IOPipeline import IOMiddleware, AsyncIOMiddleware

logger = logging.getLogger(__name__)


class CryptMiddleware(IOMiddleware):
    """Middleware síncrono de criptografia."""

    def __init__(self, crypt) -> None:
        self.crypt = crypt

    def process_inbound(self, data: bytes, ctx=None) -> bytes:
        if self.crypt and self.crypt.sync_crypt:
            try:
                return self.crypt.sync_crypt.decrypt_message(data)
            except Exception as e:
                logger.error(f"CryptMiddleware: erro no decrypt: {e}")
        return data

    def process_outbound(self, data: bytes, ctx=None) -> bytes:
        if self.crypt and self.crypt.sync_crypt:
            try:
                return self.crypt.sync_crypt.encrypt_message(data)
            except Exception as e:
                logger.error(f"CryptMiddleware: erro no encrypt: {e}")
        return data


class AsyncCryptMiddleware(AsyncIOMiddleware):
    """Middleware assíncrono de criptografia (usa async_executor do sync_crypt)."""

    def __init__(self, crypt) -> None:
        self.crypt = crypt

    async def process_inbound(self, data: bytes, ctx=None) -> bytes:
        if self.crypt and self.crypt.sync_crypt:
            try:
                return await self.crypt.sync_crypt.async_executor(
                    self.crypt.sync_crypt.decrypt_message, data)
            except Exception as e:
                logger.error(f"AsyncCryptMiddleware: erro no decrypt: {e}")
        return data

    async def process_outbound(self, data: bytes, ctx=None) -> bytes:
        if self.crypt and self.crypt.sync_crypt:
            try:
                return await self.crypt.sync_crypt.async_executor(
                    self.crypt.sync_crypt.encrypt_message, data)
            except Exception as e:
                logger.error(f"AsyncCryptMiddleware: erro no encrypt: {e}")
        return data
