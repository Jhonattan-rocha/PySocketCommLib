"""
Utilitários internos compartilhados entre Server e Client.
"""
import struct
from typing import Union


def extract_message_length(data: Union[int, float, str, bytes, bytearray]) -> int:
    """
    Extrai o comprimento de uma mensagem a partir de dados que podem vir
    em diferentes formatos (int, str, bytes com struct pack !Q).

    Usado pelo protocolo interno de framing: os primeiros 8 bytes de cada
    mensagem carregam o comprimento total como um unsigned long long big-endian.
    """
    if isinstance(data, (int, float)):
        return int(data)

    if isinstance(data, str):
        try:
            return int(data)
        except ValueError:
            pass

    if isinstance(data, (bytes, bytearray)):
        try:
            return int(data)
        except (ValueError, TypeError):
            pass
        try:
            return struct.unpack("!Q", data)[0]
        except struct.error:
            pass

    raise ValueError(f"Não foi possível extrair comprimento de: {type(data).__name__} {data!r}")
