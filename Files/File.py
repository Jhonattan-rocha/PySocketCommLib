from concurrent.futures import ThreadPoolExecutor
import os
import asyncio
from typing import Callable, Any

class File:
    def __init__(self, path: str, mode: str) -> None:
        self.path = path
        self.mode = mode
        self.file = None

    def open(self):
        try:
            if self.file is None:
                if os.path.exists(self.path) and os.path.isfile(self.path):
                    self.file = open(self.path, self.mode)
                    return self.file
                else:
                    raise FileNotFoundError(f"Arquivo não encontrado: {self.path}")
            else:
                raise RuntimeError(f"O arquivo já está aberto: {self.path}")
        except OSError as ose:
            raise OSError(f"Erro ao abrir o arquivo: {ose}")

    def read(self, chunk_size: int = 4 * 1024):
        try:
            while True:
                chunk = self.file.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except AttributeError:
            raise RuntimeError("O arquivo não está aberto.")

    def size(self):
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            raise FileNotFoundError(f"O arquivo não existe: {self.path}")

    def close(self):
        try:
            if self.file:
                self.file.close()
                self.file = None
            else:
                raise RuntimeError("O arquivo já está fechado ou não existe.")
        except OSError as ose:
            raise OSError(f"Erro ao fechar o arquivo: {ose}")

    def delete(self):
        if os.path.exists(self.path):
            try:
                if self.file:
                    self.file.close()
                os.unlink(self.path)
            except OSError as ose:
                raise OSError(f"Erro ao deletar o arquivo: {ose}")
        else:
            raise FileNotFoundError("O arquivo não existe.")

    def get_full_path(self):
        return os.path.realpath(self.path)

    async def async_execute(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res