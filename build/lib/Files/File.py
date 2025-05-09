from concurrent.futures import ThreadPoolExecutor
import os
import asyncio
from typing import Callable, Any
import io
import gzip


class File:
    def __init__(self, path: str = "", mode: str = "+ab", encoding: str = "utf8") -> None:
        self.path = path
        self.mode = mode
        self.file = None
        self.encoding = encoding

    def compress_file(self):
        bytes_c = gzip.compress(self.file.read())
        self.file = io.BytesIO(bytes_c)

    def decompress_bytes(self):
        bytes_d = gzip.decompress(self.file.read())
        self.file = io.BytesIO(bytes_d)

    def save(self, override: bool = False):
        if self.path and (not os.path.exists(self.path) or override):
            with open(self.path, "wb") as file:
                file.write(self.file.read())

    def get_name_ext(self) -> tuple[str, str]:
        return os.path.splitext(self.path)

    def setBytes(self, bytes: bytes):
        self.file = io.BytesIO(bytes)

    def open(self):
        try:
            if os.path.exists(self.path) and os.path.isfile(self.path):
                if 'b' in self.mode:
                    self.file = open(self.path, self.mode)
                else:
                    self.file = open(self.path, self.mode, encoding=self.encoding)
            else:
                raise FileNotFoundError(f"Arquivo não encontrado: {self.path}")
        except OSError as ose:
            raise OSError(f"Erro ao abrir o arquivo: {ose}")

    def read(self, chunk_size: int = 4 * 1024 * 1024):
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

    def set_full_path(self, path: str):
        if not os.path.exists(path):
            self.path = path

    def get_full_path(self):
        return os.path.realpath(self.path)

    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res


if __name__ == "__main__":
    file = File(r"C:\\Users\\Jhinattan Rocha\\Pictures\\nada.jpeg", "rb")
    file.open()

    print(file.size())
