import asyncio
import re
from Files.File import File
from Options.Ops import Client_ops
from Crypt.Crypt_main import Crypt

class Client:
    def __init__(self, Options: Client_ops) -> None:
        self.HOST = Options.host
        self.PORT = Options.port
        self.BYTES = Options.bytes
        self.loop = asyncio.get_event_loop()
        self.__running: bool = True
        self.reader = None
        self.writer = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)
    
    async def send_file(self, file: File) -> None:
        lenght = await file.async_executor(file.size)
        
        await self.send_message(re.sub(r"\D+", "", str(lenght)).encode())
        
        for chunk in await file.async_executor(file.read, 2048):
            if not chunk:
                break
            await self.send_message(chunk)
    
    async def recive_file(self) -> File:
        lenght = await self.recive_message()
        lenght = int(re.sub(r"\D+", "", lenght.decode()))
        
        chunks = b""
        bytes_rec = 0
        while bytes_rec < lenght:
            chunk = await self.recive_message()
            if not chunk:
                break
            chunks += chunk
            bytes_rec += len(chunk)
        
        file = File()
        await file.async_executor(file.setFile, chunks)
        return file

    async def sync_crypt_key(self):
        key_to_send = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.public_key_to_bytes)
        self.writer.write(key_to_send)
        await self.writer.drain()

        enc_key = await self.reader.read(2048)
        key = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.decrypt_with_private_key, enc_key)
        await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.set_key, key)
    
    async def is_running(self) -> bool:
        return self.__running
    
    async def send_message(self, message):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass
        
        lng = len(message)
        self.writer.write(lng.to_bytes(4, byteorder='big'))
        await self.writer.drain()
        
        self.writer.write(message)
        await self.writer.drain()

    async def recive_message(self):
        length_bytes = await self.reader.read(4)
        length = int.from_bytes(length_bytes, byteorder='big')
        res = await self.reader.read(length)
        try:
            return await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, res)
        except Exception as e:
            return res
    
    async def connect(self, ignore_err=False) -> None:
        try:
            if not self.reader and not self.writer:
                self.reader, self.writer = await asyncio.open_connection(self.HOST, self.PORT)
                await self.sync_crypt_key()

                print(b"Conectado")
                file = await self.recive_file()
                await file.async_executor(file.set_full_path, "./nada.jpeg")
                await file.async_executor(file.save)
            elif not ignore_err:
                raise RuntimeError("Conexão já estabelecida")
        except Exception as e:
            print(e)

    async def start(self) -> None:
        await self.connect(False)

if __name__ == "__main__":
    client = Client()
    asyncio.run(client.start())
