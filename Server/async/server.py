import asyncio

from Options.Ops import Server_ops
from Crypt.Crypt_main import Crypt
from Client.Thread.Client import Client

class Server:
    def __init__(self, Options: Server_ops) -> None:
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.loop = asyncio.get_running_loop()
        self.__clients: list[str, type[list[type[tuple], type[Client]]]] = []
        self.__running: bool = True
        self.crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)

    async def send_message(self, message: bytes, writer: asyncio.StreamWriter) -> None:
        try:
            message = await self.crypt.sync_crypt.async_execute(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass
        
        lng = len(message)
        writer.write(lng.to_bytes(4, byteorder='big'))
        await writer.drain()
        
        writer.write(message)
        await writer.drain()

    async def recive_message(self, reader: asyncio.StreamReader) -> bytes:
        length_bytes = await reader.read(4)
        length = int.from_bytes(length_bytes, byteorder='big')
        res = await reader.read(length)
        
        try:
            return await self.crypt.sync_crypt.async_execute(self.crypt.sync_crypt.decrypt_message, res)
        except Exception as e:
            return res
        
    async def is_running(self) -> bool:
        return self.__running

    async def save_clients(self, client) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
    
    async def sync_crypt_key(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_public_key = await reader.read(2048)        
        client_public_key_obj = await self.crypt.async_crypt.async_execute(self.crypt.async_crypt.load_public_key, client_public_key)
        
        sync_key = await self.crypt.sync_crypt.async_execute(self.crypt.sync_crypt.get_key)
        enc_key = await self.crypt.async_crypt.async_execute(self.crypt.async_crypt.encrypt_with_public_key, sync_key, client_public_key_obj)
        writer.write(enc_key)
        await writer.drain()
        
    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        print(f"Cliente conectado")
        await self.sync_crypt_key(reader, writer)
        await self.send_message(b"Hellow Async World", writer)

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
