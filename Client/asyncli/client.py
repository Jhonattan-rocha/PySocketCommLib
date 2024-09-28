import asyncio
import ssl
import struct
import uuid
from Events import Events
from Files import File
from Options import Client_ops, SSLContextOps
from Crypt import Crypt
from TaskManager import AsyncTaskManager
from Protocols import config


class Client:
    def __init__(self, Options: Client_ops) -> None:
        self.client_options = Options
        self.HOST = Options.host
        self.PORT = Options.port
        self.auth = Options.auth
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.uuid = uuid.uuid4()
        self.loop = asyncio.get_event_loop()
        self.events = Events()
        self.taskManager = AsyncTaskManager()
        self.configureProtocol = config
        self.__running: bool = True
        self.reader = None
        self.writer = None
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
        # Define o contexto SSL
        self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.ssl_context.load_cert_chain(certfile=ssl_ops.CERTFILE, keyfile=ssl_ops.KEYFILE)
        self.ssl_context.check_hostname = ssl_ops.check_hostname

        if ssl_ops.SERVER_CERTFILE:
            # Carrega manualmente o certificado do servidor
            self.ssl_context.load_verify_locations(cafile=ssl_ops.SERVER_CERTFILE)

    async def send_file(self, file: File, bytes_block_length: int = 2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]),
                                bytes_block_length)

    async def receive_file(self, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = await self.receive_message(bytes_block_length)
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

    async def send_message(self, message: bytes, sent_bytes: int = 2048, block: bool = False):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            pass

        try:
            message = await self.encoder(message)
        except Exception as e:
            pass

        lng = len(message)
        self.writer.write(await self.encoder(struct.pack("!Q", lng)))
        await self.writer.drain()

        if block:
            self.writer.write(message)
            await self.writer.drain()
            return

        offset = 0
        while offset < lng:
            self.writer.write(message[offset:offset + sent_bytes])
            await self.writer.drain()
            offset += sent_bytes

    async def receive_message(self, recv_bytes: int = 2048, block: bool = False):
        lng = await self.reader.read(8)
        length = struct.unpack("!Q", await self.decoder(lng))[0]

        if block:
            message = self.reader.read(length)
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
            chunk = await self.reader.read(recv_bytes)
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

    async def disconnect(self):
        self.writer.close()
        await self.writer.wait_closed()
        self.__running = False

    async def connect(self, ignore_err=False) -> None:
        try:
            if not self.reader and not self.writer:
                self.reader, self.writer = await asyncio.open_connection(self.HOST, self.PORT, ssl=self.ssl_context)

                try:
                    if self.crypt.async_crypt and self.crypt.sync_crypt:
                        await self.sync_crypt_key()
                except Exception as e:
                    pass

                try:
                    if self.auth and not self.auth.validate_token(self):
                        await self.disconnect()
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
