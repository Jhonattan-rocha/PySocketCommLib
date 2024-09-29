import asyncio
import ssl
import struct
import sys
from Abstracts.Auth import Auth
from Events import Events
from Files import File
from Options import Client_ops, SSLContextOps, Server_ops
from Crypt import Crypt
from Client import AsyncClient
from TaskManager import AsyncTaskManager
from Protocols.configure import config


class Server:
    def __init__(self, Options: Server_ops) -> None:
        self.server_options = Options
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.auth: Auth = Options.auth
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.loop = asyncio.get_running_loop()
        self.events = Events()
        self.taskManager = AsyncTaskManager()
        self.configureProtocol = config
        self.configureConnection = {}
        self.__clients: list[AsyncClient] = []
        self.__running: bool = True
        self.crypt: Crypt | None = None
        self.ssl_context: ssl.SSLContext | None = None

        if Options.ssl_ops:
            self.ssl_context: ssl.SSLContext = Options.ssl_ops.ssl_context
            if Options.ssl_ops.KEYFILE and Options.ssl_ops.CERTFILE:
                self.ssl_configure(Options.ssl_ops)

        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)

    def ssl_configure(self, ssl_ops: SSLContextOps):
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.check_hostname = ssl_ops.check_hostname
        self.ssl_context.load_cert_chain(certfile=ssl_ops.CERTFILE, keyfile=ssl_ops.KEYFILE)

    async def send_file(self, writer: asyncio.StreamWriter, file: File, bytes_block_length: int = 2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]),
                                bytes_block_length, writer)

    async def receive_file(self, reader: asyncio.StreamReader, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = await self.receive_message(bytes_block_length, reader)
        await file.async_executor(file.setBytes, bytes_recv)
        await file.async_executor(file.decompress_bytes)
        return file

    async def send_message_all_clients(self, message: bytes, sent_bytes: int = 2048):
        for client in self.__clients:
            await self.send_message(message, sent_bytes, client.writer)

    async def send_message(self, message: bytes, sent_bytes: int = 2048, writer: asyncio.StreamWriter = None, block: bool = False):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass

        try:
            message = await self.encoder(message)
        except Exception as e:
            pass

        lng = len(message)
        writer.write(await self.encoder(struct.pack("!Q", lng)))
        await writer.drain()

        if block:
            writer.write(message)
            await writer.drain()
            return

        offset = 0
        while offset < lng:
            writer.write(message[offset:offset + sent_bytes])
            await writer.drain()
            offset += sent_bytes

    async def __extract_number(self, data):
        if isinstance(data, (int, float)):
            return data

        if isinstance(data, (str, bytes)):
            try:
                return int(data)
            except Exception as e:
                pass

        if isinstance(data, (bytes, bytearray)):
            try:
                decoded_value = struct.unpack("!Q", data)[0]
                return decoded_value
            except struct.error:
                pass

    async def receive_message(self, recv_bytes: int = 2048, reader: asyncio.StreamReader = None, block: bool = False):
        length = await self.__extract_number(await self.decoder(await reader.read(8)))

        if block:
            message = reader.read(length)
            try:
                dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, await self.decoder(message))
                if await self.events.async_executor(self.events.size) > 0:
                    await self.events.async_executor(self.events.scam, dec)
                return dec
            except Exception as e:
                print(e)
                return await self.decoder(message)

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
            dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, await self.decoder(res))
            if await self.events.async_executor(self.events.size) > 0:
                await self.events.async_executor(self.events.scam, dec)
            return dec
        except Exception as e:
            return await self.decoder(res)

    async def is_running(self) -> bool:
        return self.__running

    async def save_clients(self, client: AsyncClient) -> None:
        if client not in self.__clients:
            self.__clients.append(client)

    async def sync_crypt_key(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_public_key = await reader.read(2048)
        client_public_key_obj = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.load_public_key,
                                                                            client_public_key)

        sync_key = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.get_key)
        enc_key = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.encrypt_with_public_key, sync_key,
                                                              client_public_key_obj)
        writer.write(enc_key)
        await writer.drain()

    async def get_client(self, uuid: str = "") -> AsyncClient:
        if not uuid and len(self.__clients):
            return self.__clients.pop()
        for client in self.__clients:
            if str(client.uuid) == uuid:
                return client

    async def handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        for key, value in enumerate(self.configureConnection):
            await value(reader, writer)

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        print(f"Cliente conectado")
        try:
            try:
                await self.handshake(reader, writer)
            except Exception as e:
                pass
            
            if self.crypt.async_crypt and self.crypt.sync_crypt:
                await self.sync_crypt_key(reader, writer)

            client = AsyncClient(Client_ops(host=self.HOST, port=self.PORT, ssl_ops=self.server_options.ssl_ops,
                                       encrypt_configs=self.server_options.encrypt_configs))
            client.reader = reader
            client.writer = writer

            try:
                if self.auth and not await self.auth.async_executor(self.auth.validate_token, client):
                    await client.disconnect()
                    return
            except Exception as e:
                pass

            await self.save_clients(client)
        except Exception as e:
            print(e)

    async def break_server(self):
        for client in self.__clients:
            await client.disconnect()
        self.__running = False
        sys.exit(0)

    async def start(self) -> None:
        try:
            # Criação do servidor
            server = await asyncio.start_server(
                self.run, self.HOST, self.PORT, ssl=self.ssl_context)

            addr = server.sockets[0].getsockname()
            print(f'Server rodando no endereço:{addr}')

            self.__running = True
            async with server:
                await server.serve_forever()
        except Exception as e:
            self.__running = False
            print(e)


if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
