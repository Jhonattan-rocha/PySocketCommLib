import asyncio
import re
import struct
from Events.Events import Events
from Files.File import File
from Options.Ops import Server_ops
from Crypt.Crypt_main import Crypt
from Client.Thread.Client import Client

class Server:
    def __init__(self, Options: Server_ops) -> None:
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.loop = asyncio.get_running_loop()
        self.events = Events()
        self.__clients: list[str, type[list[type[tuple], type[Client]]]] = []
        self.__running: bool = True
        self.crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)

    async def send_file(self, writer: asyncio.StreamWriter, file: File, bytes_block_length: int=2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]), bytes_block_length, writer)
    
    async def recive_file(self, reader: asyncio.StreamReader, bytes_block_length: int=2048) -> File:
        file = File()
        bytes_recv = await self.recive_message(bytes_block_length, reader)
        await file.async_executor(file.setBytes, bytes_recv)
        await file.async_executor(file.decompress_bytes)
        return file

    async def send_message(self, message: bytes, sent_bytes: int=2048, writer: asyncio.StreamWriter=None):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass
        
        lng = len(message)
        writer.write(struct.pack("!Q", lng))
        await writer.drain()
        
        offset = 0
        while offset < lng:
            writer.write(message[offset:offset + sent_bytes])
            await writer.drain()
            offset += sent_bytes

    async def recive_message(self, recv_bytes: int=2048, reader: asyncio.StreamReader=None):
        length = struct.unpack("!Q", await reader.read(8))[0]

        chunks = []
        bytes_received = 0
        while bytes_received < length:
            chunk = await reader.read(recv_bytes)
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        res = b"".join(chunks)
        try:
            dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, res)
            if await self.events.async_executor(self.events.size) > 0:
                await asyncio.create_task(self.events.async_scam(dec))
            return dec
        except Exception as e:
            print(e)
            return res
        
    async def is_running(self) -> bool:
        return self.__running

    async def save_clients(self, client) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
    
    async def sync_crypt_key(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_public_key = await reader.read(2048)        
        client_public_key_obj = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.load_public_key, client_public_key)
        
        sync_key = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.get_key)
        enc_key = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.encrypt_with_public_key, sync_key, client_public_key_obj)
        writer.write(enc_key)
        await writer.drain()
        
    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        print(f"Cliente conectado")
        try:
            if self.crypt.async_crypt and self.crypt.sync_crypt:
                await self.sync_crypt_key(reader, writer)
        except Exception as e:
            pass
        
        await self.send_message(b"!{message}:{Mensagem enviada do servidor para o cliente}!", 4*1024*1024, writer)
        
    async def start(self) -> None:
        # Criação do servidor
        server = await asyncio.start_server(
            self.run, self.HOST, self.PORT)

        addr = server.sockets[0].getsockname()
        print(f'Server rodando no endereço:{addr}')

        async with server:
            await server.serve_forever()
    
if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
