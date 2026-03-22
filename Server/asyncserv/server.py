import asyncio
import ssl
import struct
import logging
from typing import Optional, List, Dict, Any
from ...Abstracts.Auth import Auth
from ...Auth.NoAuth import NoAuth
from ...Auth.SimpleAuth import SimpleTokenAuth
from ...Events import Events
from ...Files import File
from ...Options import Client_ops, SSLContextOps, Server_ops
from ...Crypt import Crypt
from ...Client import AsyncClient
from ..helpers.rateLimit import TokenBucket as AsyncTokenBucket
from ...TaskManager import AsyncTaskManager

logger = logging.getLogger(__name__)


def setup_logging(log_file: Optional[str] = None, log_level: int = logging.INFO,
                  log_format: Optional[str] = None) -> None:
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logger.handlers.clear()
    logger.setLevel(log_level)

    formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info("Logging configurado com sucesso")


class AsyncServer:
    def __init__(self, options: Server_ops) -> None:
        self.server_options = options
        self.HOST: str = options.host
        self.PORT: int = options.port
        self.auth: Optional[Auth] = options.auth
        self.auth_method: str = options.auth_method
        self.auth_config: Dict[str, Any] = options.auth_config or {}
        self.encoder = options.encoder
        self.decoder = options.decoder

        self.events = Events()
        self.task_manager = AsyncTaskManager()
        self.server: Optional[asyncio.Server] = None
        self.configure_connection: Dict[str, Any] = {}
        self.__clients: List[AsyncClient] = []
        self.__running: bool = False
        self.crypt: Optional[Crypt] = None
        self.ssl_context: Optional[ssl.SSLContext] = None
        self.rate_limits: Dict[str, AsyncTokenBucket] = {}

        log_file = getattr(options, 'log_file', None)
        log_level = getattr(options, 'log_level', logging.INFO)
        setup_logging(log_file, log_level)

        if options.ssl_ops:
            self.ssl_context = options.ssl_ops.ssl_context
            if options.ssl_ops.KEYFILE and options.ssl_ops.CERTFILE:
                self.ssl_configure(options.ssl_ops)

        if options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(options.encrypt_configs)
            logger.info("Criptografia habilitada")

        if not self.auth:
            self.auth = self._create_auth_instance()

        logger.info(f"AsyncServer inicializado em {self.HOST}:{self.PORT}")

    def _create_auth_instance(self) -> Auth:
        try:
            auth_method_name = self.auth_method.lower()

            if auth_method_name in ['none', 'noauth']:
                logger.info("Usando NoAuth")
                return NoAuth()
            elif auth_method_name in ['simple', 'simpleauth', 'token']:
                logger.info("Usando SimpleTokenAuth")
                token = self.auth_config.get('token')
                if not token:
                    raise ValueError("SimpleTokenAuth requer 'token' em auth_config.")
                return SimpleTokenAuth(token=token)
            else:
                raise ValueError(f"Método de autenticação não suportado: {self.auth_method}")

        except Exception as e:
            logger.error(f"Falha ao criar instância de autenticação: {e}")
            logger.info("Usando NoAuth como fallback")
            return NoAuth()

    def ssl_configure(self, ssl_ops: SSLContextOps):
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.check_hostname = ssl_ops.check_hostname
        self.ssl_context.load_cert_chain(certfile=ssl_ops.CERTFILE, keyfile=ssl_ops.KEYFILE)
        logger.info("Configuração SSL aplicada.")

    async def send_file(self, writer: asyncio.StreamWriter, file: File, bytes_block_length: int = 2048) -> None:
        await file.async_executor(file.compress_file)
        data = b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)])
        await self.send_message(data, bytes_block_length, writer)
        logger.debug(f"Arquivo enviado para {writer.get_extra_info('peername')}: {file.path}")

    async def receive_file(self, reader: asyncio.StreamReader, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = await self.receive_message(bytes_block_length, reader)
        await file.async_executor(file.setBytes, bytes_recv)
        await file.async_executor(file.decompress_bytes)
        logger.debug(f"Arquivo recebido do cliente {reader.get_extra_info('peername')}")
        return file

    async def send_message_all_clients(self, message: bytes, sent_bytes: int = 2048):
        logger.info("Enviando mensagem para todos os clientes.")
        for client in self.__clients:
            await self.send_message(message, sent_bytes, client.writer)

    async def send_message(self, message: bytes, sent_bytes: int = 2048,
                           writer: asyncio.StreamWriter = None, block: bool = False):
        if self.crypt and self.crypt.sync_crypt:
            try:
                message = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.encrypt_message, message)
            except Exception as e:
                logger.error(f"Erro ao criptografar mensagem: {e}")

        encoded = self.encoder(message)
        lng = len(encoded)

        try:
            writer.write(self.encoder(struct.pack("!Q", lng)))
            await writer.drain()
        except Exception as e:
            logger.error(f"Erro ao enviar tamanho da mensagem para {writer.get_extra_info('peername')}: {e}")
            return

        if block:
            try:
                writer.write(encoded)
                await writer.drain()
                return
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem bloqueada para {writer.get_extra_info('peername')}: {e}")

        offset = 0
        while offset < lng:
            try:
                writer.write(encoded[offset:offset + sent_bytes])
                await writer.drain()
                offset += sent_bytes
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para {writer.get_extra_info('peername')}: {e}")
                return

    def __extract_number(self, data):
        if isinstance(data, (int, float)):
            return data

        if isinstance(data, str):
            try:
                return int(data)
            except Exception:
                pass

        if isinstance(data, (bytes, bytearray)):
            try:
                return int(data)
            except Exception:
                pass
            try:
                return struct.unpack("!Q", data)[0]
            except struct.error:
                pass

    async def receive_message(self, recv_bytes: int = 2048,
                              reader: asyncio.StreamReader = None, block: bool = False):
        client = None
        for cli in self.__clients:
            if cli.reader == reader:
                client = cli
                break

        if client is not None:
            uuid = str(client.uuid)
            if uuid not in self.rate_limits:
                self.rate_limits[uuid] = AsyncTokenBucket(rate=2, capacity=5)

            bucket = self.rate_limits[uuid]
            if not await bucket.allow():
                logger.warning(f"Rate limit excedido para o cliente {uuid}")
                await self.send_message(b"Rate limit excedido. Aguarde.", writer=client.writer)
                return b""

        try:
            length_bytes = await reader.read(8)
            if not length_bytes:
                return b""
            length = self.__extract_number(self.decoder(length_bytes))
        except Exception as e:
            logger.error(f"Erro ao receber tamanho da mensagem de {reader.get_extra_info('peername')}: {e}")
            return b""

        if block:
            try:
                message_bytes = await reader.read(length)
                raw = self.decoder(message_bytes)
                if self.crypt and self.crypt.sync_crypt:
                    dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, raw)
                else:
                    dec = raw
                if await self.events.async_executor(self.events.size) > 0:
                    await self.events.async_executor(self.events.scan, dec)
                return dec
            except Exception as e:
                logger.error(f"Erro ao decriptar mensagem bloqueada de {reader.get_extra_info('peername')}: {e}")
                return b""

        chunks = []
        bytes_received = 0
        while bytes_received < length:
            try:
                chunk = await reader.read(recv_bytes)
            except Exception as e:
                logger.error(f"Erro ao receber chunk de {reader.get_extra_info('peername')}: {e}")
                raise RuntimeError('Conexão interrompida') from e

            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        res = b"".join(chunks)
        raw = self.decoder(res)
        try:
            if self.crypt and self.crypt.sync_crypt:
                dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, raw)
            else:
                dec = raw
            if await self.events.async_executor(self.events.size) > 0:
                await self.events.async_executor(self.events.scan, dec)
            return dec
        except Exception as e:
            logger.error(f"Erro ao decriptar mensagem de {reader.get_extra_info('peername')}: {e}")
            return raw

    def is_running(self) -> bool:
        return self.__running

    async def save_clients(self, client: AsyncClient) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
            logger.info(f"Cliente conectado: {client.writer.get_extra_info('peername')}, UUID: {client.uuid}")

    async def sync_crypt_key(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            client_public_key = self.decoder(await reader.read(2048))
            client_public_key_obj = await self.crypt.async_crypt.async_executor(
                self.crypt.async_crypt.load_public_key, client_public_key)

            sync_key = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.get_key)
            enc_key = await self.crypt.async_crypt.async_executor(
                self.crypt.async_crypt.encrypt_with_public_key, sync_key, client_public_key_obj)
            writer.write(self.encoder(enc_key))
            await writer.drain()
            logger.debug(f"Chaves sincronizadas com {writer.get_extra_info('peername')}")
        except Exception as e:
            logger.error(f"Erro na sincronização de chaves com {writer.get_extra_info('peername')}: {e}")

    async def get_client(self, uuid: str = "") -> Optional[AsyncClient]:
        if not uuid and len(self.__clients) == 1:
            return self.__clients[0]
        for client in self.__clients:
            if str(client.uuid) == uuid:
                return client
        return None

    async def check_is_close(self):
        while self.__running:
            closed = [cli for cli in self.__clients if cli.writer.is_closing()]
            for cli in closed:
                self.__clients.remove(cli)
                logger.info(f"Cliente removido (conexão encerrada): {cli.uuid}")
            await asyncio.sleep(10)

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        address = writer.get_extra_info('peername')
        logger.info(f"Nova conexão: {address}")
        try:
            client = AsyncClient(Client_ops(host=self.HOST, port=self.PORT,
                                            ssl_ops=self.server_options.ssl_ops,
                                            encrypt_configs=self.server_options.encrypt_configs))
            client.reader = reader
            client.writer = writer

            try:
                if self.auth and not self.auth.validate_token(client):
                    await client.disconnect()
                    logger.warning(f"Cliente {address} desconectado: falha na autenticação.")
                    return
            except Exception as e:
                logger.error(f"Erro durante a autenticação do cliente {address}: {e}")

            await self.save_clients(client)

        except Exception as e:
            logger.error(f"Erro ao lidar com cliente {address}: {e}")
        finally:
            logger.info(f"Handler de {address} finalizado.")

    async def break_server(self):
        logger.info("Servidor Async sendo interrompido...")
        if not self.server:
            logger.error("Servidor não iniciado")
            return

        self.__running = False
        for client in self.__clients:
            await client.disconnect()

        self.server.close()
        await self.server.wait_closed()

    async def start(self) -> None:
        try:
            server = await asyncio.start_server(
                self.run, self.HOST, self.PORT, ssl=self.ssl_context)

            self.server = server
            self.__running = True

            addr = server.sockets[0].getsockname()
            logger.info(f'Servidor Async rodando em: {addr}')

            asyncio.create_task(self.check_is_close())

            async with server:
                await server.serve_forever()
        except Exception as e:
            self.__running = False
            logger.error(f"Erro ao iniciar o servidor Async: {e}")
