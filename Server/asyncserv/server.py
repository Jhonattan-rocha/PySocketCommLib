import asyncio
import ssl
import struct
import logging 
from Abstracts.Auth import Auth
from Auth.NoAuth import NoAuth
from Auth.SimpleAuth import SimpleTokenAuth
from Events import Events
from Files import File
from Options import Client_ops, SSLContextOps, Server_ops
from Crypt import Crypt
from Client import AsyncClient
from Server import TokenBucket
from TaskManager import AsyncTaskManager

# Configuração básica do logger para salvar em arquivo
logging.basicConfig(filename='./server_async.txt',  # Nome do arquivo de log
                    level=logging.INFO,  # Nível de log padrão
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)  # Logger para o módulo atual


class Server:
    def __init__(self, Options: Server_ops) -> None:
        self.server_options = Options
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.auth: Auth = Options.auth
        self.auth_method: str = Options.auth_method
        self.auth_config: dict = Options.auth_config
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.loop = asyncio.get_running_loop()
        self.events = Events()
        self.taskManager = AsyncTaskManager()
        self.server: asyncio.Server | None = None
        self.configureConnection = {}
        self.__clients: list[AsyncClient] = []
        self.__running: bool = True
        self.crypt: Crypt | None = None
        self.ssl_context: ssl.SSLContext | None = None
        self.rate_limits: dict[str, TokenBucket] = {}  # uuid -> TokenBucket

        if Options.ssl_ops:
            self.ssl_context: ssl.SSLContext = Options.ssl_ops.ssl_context
            if Options.ssl_ops.KEYFILE and Options.ssl_ops.CERTFILE:
                self.ssl_configure(Options.ssl_ops)

        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)

        if not self.auth:
            self.auth = self._create_auth_instance()

        logger.info(f"Servidor Async inicializado em {self.HOST}:{self.PORT}")

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
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.check_hostname = ssl_ops.check_hostname
        self.ssl_context.load_cert_chain(certfile=ssl_ops.CERTFILE, keyfile=ssl_ops.KEYFILE)
        logger.info("Configuração SSL aplicada.")

    async def send_file(self, writer: asyncio.StreamWriter, file: File, bytes_block_length: int = 2048) -> None:
        await file.async_executor(file.compress_file)
        await self.send_message(b"".join([chunk for chunk in await file.async_executor(file.read, bytes_block_length)]),
                                 bytes_block_length, writer)
        logger.debug(f"Arquivo enviado para o cliente {writer.get_extra_info('peername')}: {file.name}")

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

    async def send_message(self, message: bytes, sent_bytes: int = 2048, writer: asyncio.StreamWriter = None, block: bool = False):
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
            writer.write(await self.encoder(struct.pack("!Q", lng)))
            await writer.drain()
        except Exception as e:
            logger.error(f"Erro ao enviar tamanho da mensagem para o cliente {writer.get_extra_info('peername')}: {e}")
            return

        if block:
            try:
                writer.write(message)
                await writer.drain()
                logger.debug(f"Mensagem bloqueada enviada para o cliente {writer.get_extra_info('peername')}: {message[:50]}...")
                return
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem bloqueada para o cliente {writer.get_extra_info('peername')}: {e}")

        offset = 0
        while offset < lng:
            try:
                writer.write(message[offset:offset + sent_bytes])
                await writer.drain()
                offset += sent_bytes
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para o cliente {writer.get_extra_info('peername')}: {e}")
                return
        logger.debug(f"Mensagem enviada para o cliente {writer.get_extra_info('peername')}: {message[:50]}...")

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
        client = None

        for cli in self.__clients:
            if cli.reader == reader:
                client = cli
        
        uuid = client.uuid 

        if uuid not in self.rate_limits:
            self.rate_limits[uuid] = TokenBucket(rate=2, capacity=5) 

        bucket = self.rate_limits[uuid]
        if not await bucket.allow():
            logger.warning(f"Rate limit excedido para o cliente {uuid}")
            await client.send_message(b"Rate limit excedido. Aguarde.")
            return

        try:
            length_bytes = await reader.read(8)
            if not length_bytes:
                return b""  # Retorna bytes vazios se a conexão for fechada
            length = await self.__extract_number(await self.decoder(length_bytes))
        except Exception as e:
            logger.error(f"Erro ao receber o tamanho da mensagem do cliente {reader.get_extra_info('peername')}: {e}")
            return b""

        if block:
            try:
                message_bytes = await reader.read(length)
                dec = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.decrypt_message, await self.decoder(message_bytes))
                if await self.events.async_executor(self.events.size) > 0:
                    await self.events.async_executor(self.events.scam, dec)
                logger.debug(f"Mensagem bloqueada recebida do cliente {reader.get_extra_info('peername')}: {dec[:50]}...")
                return dec
            except Exception as e:
                logger.error(f"Erro ao decriptar mensagem bloqueada ou scam evento do cliente {reader.get_extra_info('peername')}: {e}")
                return await self.decoder(message_bytes)

        chunks = []
        bytes_received = 0
        while bytes_received < length:
            try:
                chunk = await reader.read(recv_bytes)
            except Exception as e:
                logger.error(f"Erro ao receber chunk da mensagem do cliente {reader.get_extra_info('peername')}: {e}")
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
            logger.debug(f"Mensagem recebida do cliente {reader.get_extra_info('peername')}: {dec[:50]}...")
            return dec
        except Exception as e:
            logger.error(f"Erro ao decriptar mensagem ou scam evento do cliente {reader.get_extra_info('peername')}: {e}")
            return await self.decoder(res)

    async def is_running(self) -> bool:
        return self.__running

    async def save_clients(self, client: AsyncClient) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
            logger.info(f"Cliente conectado: {client.writer.get_extra_info('peername')}, UUID: {client.uuid}")

    async def sync_crypt_key(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            client_public_key = self.decoder(await reader.read(2048))
            client_public_key_obj = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.load_public_key,
                                                                                    client_public_key)

            sync_key = await self.crypt.sync_crypt.async_executor(self.crypt.sync_crypt.get_key)
            enc_key = await self.crypt.async_crypt.async_executor(self.crypt.async_crypt.encrypt_with_public_key, sync_key,
                                                                    client_public_key_obj)
            writer.write(self.encoder(enc_key))
            await writer.drain()
            logger.debug(f"Chaves criptográficas sincronizadas com o cliente {writer.get_extra_info('peername')}")
        except Exception as e:
            logger.error(f"Erro na sincronização de chaves com o cliente {writer.get_extra_info('peername')}: {e}")

    async def get_client(self, uuid: str = "") -> AsyncClient:
        if not uuid and len(self.__clients) == 1:
            return self.__clients.pop()
        for client in self.__clients:
            if str(client.uuid) == uuid:
                return client
    
    async def check_is_close(self, client: AsyncClient | None = None):
        if client:
            if client.writer.is_closing():
                self.__clients.remove(client)
        else:
            while self.__running:
                for cli in self.__clients:
                    if cli.writer.is_closing:
                        self.__clients.remove(cli)
                
                asyncio.sleep(10)

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        address = writer.get_extra_info('peername')
        logger.info(f"Cliente conectado: {address}")
        try:
            client = AsyncClient(Client_ops(host=self.HOST, port=self.PORT, ssl_ops=self.server_options.ssl_ops,
                                            encrypt_configs=self.server_options.encrypt_configs))
            client.reader = reader
            client.writer = writer

            try:
                if self.auth and not await self.auth.async_executor(self.auth.validate_token, client):
                    await client.disconnect()
                    logger.warning(f"Cliente {address} desconectado devido a falha na autenticação.")
                    return
            except Exception as e:
                logger.error(f"Erro durante a autenticação do cliente {address}: {e}")

            await self.save_clients(client)

        except Exception as e:
            logger.error(f"Erro ao lidar com cliente {address}: {e}")
        finally:
            logger.info(f"Cliente desconectado: {address}")


    async def break_server(self):
        logger.info("Servidor Async sendo interrompido...")
        if not self.server:
            logger.error("Servidor não inciado")
            return
        
        for client in self.__clients:
            await client.disconnect()
        self.__running = False
        for task in asyncio.all_tasks():
            task.cancel()  

        await self.server.close()      

    async def start(self) -> None:
        try:
            # Criação do servidor
            server = await asyncio.start_server(
                self.run, self.HOST, self.PORT, ssl=self.ssl_context)
            
            self.server = server

            addr = server.sockets[0].getsockname()
            logger.info(f'Servidor Async rodando no endereço:{addr}')

            asyncio.create_task(self.check_is_close)
            self.__running = True
            async with server:
                await server.serve_forever()
        except Exception as e:
            self.__running = False
            logger.error(f"Erro ao iniciar o servidor Async: {e}")

if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
