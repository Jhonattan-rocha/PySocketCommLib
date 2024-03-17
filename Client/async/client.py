import asyncio
import re
import struct
import uuid
from Events.Events import Events
from Files.File import File
from Options.Ops import Client_ops
from Crypt.Crypt_main import Crypt
from TaskManager.AsyncTaskManager import AsyncTaskManager

class Client:
    def __init__(self, Options: Client_ops) -> None:
        self.HOST = Options.host
        self.PORT = Options.port
        self.uuid = uuid.uuid4()
        self.loop = asyncio.get_event_loop()
        self.events = Events()
        self.taskManager = AsyncTaskManager()
        self.__running: bool = True
        self.reader = None
        self.writer = None
        self.crypt: Crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)
    
    async def send_file(self, file: File, bytes_block_length: int=2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]), bytes_block_length)
    
    async def recive_file(self, bytes_block_length: int=2048) -> File:
        file = File()
        bytes_recv = await self.recive_message(bytes_block_length)
        await file.async_executor(file.setBytes, bytes_recv)
        await file.async_executor(file.decompress_bytes)
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
    
    async def send_message(self, message: bytes, sent_bytes: int=2048):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass
        
        lng = len(message)
        self.writer.write(struct.pack("!Q", lng))
        await self.writer.drain()
        
        offset = 0
        while offset < lng:
            self.writer.write(message[offset:offset + sent_bytes])
            await self.writer.drain()
            offset += sent_bytes

    async def recive_message(self, recv_bytes: int=2048):
        length = struct.unpack("!Q", await self.reader.read(8))[0]

        chunks = []
        bytes_received = 0
        while bytes_received < length:
            chunk = await self.reader.read(recv_bytes)
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        res = b"".join(chunks)
        try:
            dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, res)
            if await self.events.async_executor(self.events.size) > 0:
                await self.events.async_executor(self.events.scam, dec)
            return dec
        except Exception as e:
            print(e)
            return res
    
    async def disconnect(self):
        self.writer.close()
        await self.writer.wait_closed()
        self.__running = False
    
    async def connect(self, ignore_err=False) -> None:
        try:
            if not self.reader and not self.writer:
                self.reader, self.writer = await asyncio.open_connection(self.HOST, self.PORT)
                
                try:
                    if self.crypt.async_crypt and self.crypt.sync_crypt:
                        await self.sync_crypt_key()
                except Exception as e:
                    pass

                self.__running = True
            elif not ignore_err:
                raise RuntimeError("Conexão já estabelecida")
        except Exception as e:
            self.__running = False
            print(e)

    async def start(self) -> None:
        await self.connect(False)

if __name__ == "__main__":
    client = Client()
    asyncio.run(client.start())
