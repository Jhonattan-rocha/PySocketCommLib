"""Middleware de codec: aplica encoder em outbound e decoder em inbound."""
import logging
from typing import Callable
from ..Abstracts.IOPipeline import IOMiddleware

logger = logging.getLogger(__name__)


class CodecMiddleware(IOMiddleware):
    """Aplica decoder nos dados recebidos e encoder nos dados enviados."""

    def __init__(self, encoder: Callable, decoder: Callable) -> None:
        self.encoder = encoder
        self.decoder = decoder

    def process_inbound(self, data: bytes, ctx=None) -> bytes:
        try:
            return self.decoder(data)
        except Exception as e:
            logger.error(f"CodecMiddleware: erro no decode: {e}")
            return data

    def process_outbound(self, data: bytes, ctx=None) -> bytes:
        try:
            return self.encoder(data)
        except Exception as e:
            logger.error(f"CodecMiddleware: erro no encode: {e}")
            return data
