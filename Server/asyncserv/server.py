import asyncio
import ssl
import struct
import logging
from typing import Optional, List, Dict, Any
from ...Abstracts.Auth import Auth
from ...Abstracts.ConnectionContext import AsyncConnectionContext
from ...Abstracts.IOPipeline import AsyncIOPipeline
from .ConnectionTask import AsyncConnectionTask
from ...Abstracts.utils import extract_message_length
from ...Auth.NoAuth import NoAuth
from ...Auth.SimpleAuth import SimpleTokenAuth
from ...Events import Events
from ...Files import File
from ...Options import SSLContextOps, Server_ops
from ...Crypt import Crypt
from ...Pipeline import CodecMiddleware, AsyncCryptMiddleware, AsyncEventsMiddleware
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
        self.__clients: List[AsyncConnectionContext] = []
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

        self.pipeline = AsyncIOPipeline()
        self.pipeline.add(CodecMiddleware(self.encoder, self.decoder))
        self.pipeline.add(AsyncCryptMiddleware(self.crypt))
        self.pipeline.add(AsyncEventsMiddleware(self.events))

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
        for ctx in self.__clients:
            await self.send_message(message, sent_bytes, ctx.writer)

    async def send_message(self, message: bytes, sent_bytes: int = 2048,
                           writer: asyncio.StreamWriter = None, block: bool = False):
        encoded = await self.pipeline.process_outbound(message)
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

    async def receive_message(self, recv_bytes: int = 2048,
                              reader: asyncio.StreamReader = None, block: bool = False):
        # Localiza o contexto pelo reader para aplicar rate limiting
        ctx = next((c for c in self.__clients if c.reader == reader), None)

        if ctx is not None:
            if ctx.uuid not in self.rate_limits:
                self.rate_limits[ctx.uuid] = AsyncTokenBucket(rate=2, capacity=5)

            bucket = self.rate_limits[ctx.uuid]
            if not await bucket.allow():
                logger.warning(f"Rate limit excedido para o cliente {ctx.uuid}")
                await self.send_message(b"Rate limit excedido. Aguarde.", writer=ctx.writer)
                return b""

        try:
            length_bytes = await reader.read(8)
            if not length_bytes:
                return b""
            length = extract_message_length(self.decoder(length_bytes))
        except Exception as e:
            logger.error(f"Erro ao receber tamanho da mensagem de {reader.get_extra_info('peername')}: {e}")
            return b""

        if block:
            try:
                message_bytes = await reader.read(length)
                return await self.pipeline.process_inbound(message_bytes)
            except Exception as e:
                logger.error(f"Erro ao receber mensagem bloqueada de {reader.get_extra_info('peername')}: {e}")
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

        return await self.pipeline.process_inbound(b"".join(chunks))

    def is_running(self) -> bool:
        return self.__running

    def get_clients(self) -> List[AsyncConnectionContext]:
        """Retorna a lista de contextos de conexão ativos."""
        return list(self.__clients)

    async def save_clients(self, ctx: AsyncConnectionContext) -> None:
        if ctx not in self.__clients:
            self.__clients.append(ctx)
            logger.info(f"Cliente conectado: {ctx.address}, UUID: {ctx.uuid}")

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

    async def get_client(self, uuid: str = "") -> Optional[AsyncConnectionContext]:
        if not uuid and len(self.__clients) == 1:
            return self.__clients[0]
        for ctx in self.__clients:
            if ctx.uuid == uuid:
                return ctx
        return None

    async def check_is_close(self):
        while self.__running:
            closed = [ctx for ctx in self.__clients if ctx.is_closing()]
            for ctx in closed:
                self.__clients.remove(ctx)
                logger.info(f"Cliente removido (conexão encerrada): {ctx.uuid}")
            await asyncio.sleep(10)

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        address = writer.get_extra_info('peername')
        logger.info(f"Nova conexão: {address}")
        ctx = None
        try:
            ctx = AsyncConnectionContext(reader=reader, writer=writer, address=address)

            try:
                if self.auth and not self.auth.validate_token(ctx):
                    await ctx.disconnect()
                    logger.warning(f"Cliente {address} desconectado: falha na autenticação.")
                    return
            except Exception as e:
                logger.error(f"Erro durante a autenticação do cliente {address}: {e}")

            await self.save_clients(ctx)
            await self.task_manager.register_task(AsyncConnectionTask(ctx))
            self.events.emit("server.connect", ctx.uuid, ctx.address)

            # Loop de mensagens — mantém a conexão viva e dispara eventos
            while not writer.is_closing() and self.__running:
                try:
                    data = await self.receive_message(reader=reader)
                    if not data:
                        break
                except RuntimeError:
                    break
                except Exception as e:
                    logger.error(f"Erro no loop de mensagens de {address}: {e}")
                    break

        except Exception as e:
            logger.error(f"Erro ao lidar com cliente {address}: {e}")
        finally:
            if ctx is not None:
                if ctx in self.__clients:
                    self.__clients.remove(ctx)
                    logger.info(f"Cliente desconectado: {address}, UUID: {ctx.uuid}")
                await self.task_manager.unregister_task(ctx.uuid)
                self.events.emit("server.disconnect", ctx.uuid, ctx.address)
            if not writer.is_closing():
                writer.close()
            logger.info(f"Handler de {address} finalizado.")

    async def break_server(self):
        logger.info("Servidor Async sendo interrompido...")
        if not self.server:
            logger.error("Servidor não iniciado")
            return

        self.__running = False
        await self.task_manager.stop_all_tasks()

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
