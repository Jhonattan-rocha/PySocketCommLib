import asyncio
import ssl
import struct
import uuid
import logging 
from Abstracts.Auth import Auth
from Auth.NoAuth import NoAuth
from Auth.SimpleAuth import SimpleTokenAuth
from Events import Events
from Files import File
from Options import Client_ops, SSLContextOps
from Crypt import Crypt
from TaskManager import AsyncTaskManager


logging.basicConfig(filename='./client_async.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get logger for this module


class Client:
    def __init__(self, Options: Client_ops) -> None:
        self.client_options = Options
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.auth: Auth = Options.auth
        self.auth_method: str = Options.auth_method
        self.auth_config: dict = Options.auth_config
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.uuid = uuid.uuid4()
        self.loop = asyncio.get_event_loop()
        self.events = Events()
        self.taskManager = AsyncTaskManager()
        self.configureConnection = {}
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

        if not self.auth:
            self.auth = self._create_auth_instance()
        logger.info(f"Cliente Async inicializado com UUID: {self.uuid}")

    def _create_auth_instance(self):
        auth_method_name = self.auth_method.lower()
        if auth_method_name == 'noauth':
            return NoAuth()
        elif auth_method_name == 'simpleauth':
            token = self.auth_config.get('token')
            if not token:
                raise ValueError("SimpleTokenAuth requires 'token' in auth_config.")
            return SimpleTokenAuth(token=token)
        else:
            return NoAuth()

    def ssl_configure(self, ssl_ops: SSLContextOps):
        # Define o contexto SSL
        self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.ssl_context.load_cert_chain(certfile=ssl_ops.CERTFILE, keyfile=ssl_ops.KEYFILE)
        self.ssl_context.check_hostname = ssl_ops.check_hostname

        if ssl_ops.SERVER_CERTFILE:
            # Carrega manualmente o certificado do servidor
            self.ssl_context.load_verify_locations(cafile=ssl_ops.SERVER_CERTFILE)
        logger.info("Configuração SSL aplicada.")

    async def send_file(self, file: File, bytes_block_length: int = 2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]),
                                 bytes_block_length)
        logger.debug(f"Arquivo enviado: {file.name}")

    async def receive_file(self, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = await self.receive_message(bytes_block_length)
        await file.async_executor(file.setBytes, bytes_recv)
        await file.async_executor(file.decompress_bytes)
        logger.debug(f"Arquivo recebido.")
        return file

    async def sync_crypt_key(self):
        key_to_send = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.public_key_to_bytes)
        self.writer.write(self.encoder(key_to_send))
        await self.writer.drain()
        logger.debug("Chave pública de criptografia assimétrica enviada para o servidor.")

        enc_key = self.decoder(await self.reader.read(2048))
        key = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.decrypt_with_private_key, enc_key)
        await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.set_key, key)
        logger.debug("Chave de criptografia simétrica sincronizada com o servidor.")

    async def is_running(self) -> bool:
        return self.__running

    async def send_message(self, message: bytes, sent_bytes: int = 2048, block: bool = False):
        try:
            message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
        except Exception as e:
            logger.error(f"Erro ao criptografar mensagem: {e}")

        try:
            message = await self.encoder(message)
        except Exception as e:
            logger.error(f"Erro ao codificar mensagem: {e}")

        lng = len(message)
        try:
            self.writer.write(await self.encoder(struct.pack("!Q", lng)))
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Erro ao enviar tamanho da mensagem: {e}")
            return

        if block:
            try:
                self.writer.write(message)
                await self.writer.drain()
                logger.debug(f"Mensagem bloqueada enviada: {message[:50]}...")
                return
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem bloqueada: {e}")

        offset = 0
        while offset < lng:
            try:
                self.writer.write(message[offset:offset + sent_bytes])
                await self.writer.drain()
                offset += sent_bytes
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                return
        logger.debug(f"Mensagem enviada: {message[:50]}...")

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

    async def receive_message(self, recv_bytes: int = 2048, block: bool = False):
        try:
            lng_bytes = await self.reader.read(8)
            if not lng_bytes:
                return b""  # Retorna bytes vazios se a conexão for fechada
            length = await self.__extract_number(await self.decoder(lng_bytes))
        except Exception as e:
            logger.error(f"Erro ao receber o tamanho da mensagem: {e}")
            return b""

        if block:
            try:
                message = await self.reader.read(length)
                dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, await self.decoder(message))
                if await self.events.async_executor(self.events.size) > 0:
                    await self.events.async_executor(self.events.scam, dec)
                logger.debug(f"Mensagem bloqueada recebida: {dec[:50]}...")
                return dec
            except Exception as e:
                logger.error(f"Erro ao decriptar mensagem bloqueada ou scam evento: {e}")
                return await self.decoder(message)

        chunks = []
        bytes_received = 0
        while bytes_received < length:
            try:
                chunk = await self.reader.read(recv_bytes)
            except Exception as e:
                logger.error(f"Erro ao receber chunk da mensagem: {e}")
                raise RuntimeError('Conexão interrompida') from e # Relevando a exceção para tratamento de conexão interrompida

            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        res = b"".join(chunks)
        try:
            dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, await self.decoder(res))
            if await self.events.async_executor(self.events.size) > 0:
                await self.events.async_executor(self.events.scam, dec)
            logger.debug(f"Mensagem recebida: {dec[:50]}...")
            return dec
        except Exception as e:
            logger.error(f"Erro ao decriptar mensagem ou scam evento: {e}")
            return await self.decoder(res)

    async def disconnect(self):
        try:
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("Desconectado do servidor.")
        except Exception as e:
            logger.error(f"Erro ao desconectar: {e}")
        self.__running = False

    async def connect(self, ignore_err=False) -> None:
        try:
            if not self.reader and not self.writer:
                self.reader, self.writer = await asyncio.open_connection(self.HOST, self.PORT, ssl=self.ssl_context)
                logger.info(f"Conectado ao servidor {self.HOST}:{self.PORT} via TCP.")

                try:
                    if self.auth and not self.auth.validate_token(self):
                        await self.disconnect()
                        logger.warning("Falha na autenticação, desconectando.")
                        return
                except Exception as e:
                    logger.error(f"Erro durante a autenticação: {e}")

                self.__running = True
            elif not ignore_err:
                raise RuntimeError("Conexão já estabelecida") #This will not be raised as connection is checked at the beginning
        except Exception as e:
            self.__running = False
            logger.error(f"Erro ao conectar ao servidor: {e}")

    async def start(self) -> None:
        await self.connect(False)
        if self.is_running():
            logger.info("Cliente conectado e rodando.")
        else:
            logger.error("Cliente falhou ao conectar ou não está rodando.")


if __name__ == "__main__":
    client = Client()
    asyncio.run(client.start())
