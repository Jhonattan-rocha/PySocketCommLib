import socket
import ssl
import struct
import threading
from queue import Queue
from ...Abstracts.Auth import Auth
from ...Abstracts.ConnectionContext import ThreadConnectionContext
from ...Abstracts.IOPipeline import IOPipeline
from ...Abstracts.utils import extract_message_length
from ...Auth.NoAuth import NoAuth
from ...Auth.SimpleAuth import SimpleTokenAuth
from ...Events import Events
from ...Options import Server_ops, SSLContextOps
from ...Crypt import Crypt
from ...Connection_type.Types import Types
from ...Files import File
from ...Pipeline import CodecMiddleware, CryptMiddleware, EventsMiddleware
from ...TaskManager import TaskManager
import logging

logging.basicConfig(level=logging.INFO, filename="./server_thread.txt",
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.server_options = Options
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.auth: Auth = Options.auth
        self.auth_method: str = Options.auth_method
        self.auth_config: dict = Options.auth_config
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.conn_type: Types | tuple = Options.conn_type
        self.events = Events()
        self.taskManager = TaskManager()
        self.configureConnection = {}
        self.server_socket: socket.socket | None = None
        self.hitory_udp_message: Queue[tuple] = Queue(Options.MAX_HISTORY_UDP_MESSAGES)
        self.__clients: list[ThreadConnectionContext] = []
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

        if not self.auth:
            self.auth = self._create_auth_instance()

        self.pipeline = IOPipeline()
        self.pipeline.add(CodecMiddleware(self.encoder, self.decoder))
        self.pipeline.add(CryptMiddleware(self.crypt))
        self.pipeline.add(EventsMiddleware(self.events))

        logger.info(f"Servidor inicializado em {self.HOST}:{self.PORT} com tipo de conexão: {self.conn_type}")

    def _create_auth_instance(self):
        auth_method_name = self.auth_method.lower()
        if auth_method_name == 'noauth':
            return NoAuth()
        elif auth_method_name == 'simpletoken':
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

    def send_file(self, ctx: ThreadConnectionContext, file: File, bytes_block_length: int = 2048) -> None:
        file.compress_file()
        self.send_message(ctx.connection, b"".join([chunk for chunk in file.read(bytes_block_length)]), bytes_block_length)
        logger.debug(f"Arquivo enviado para {ctx.address}: {file.path}")

    def receive_file(self, ctx: ThreadConnectionContext, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = self.receive_message(ctx.connection, bytes_block_length)
        file.setBytes(bytes_recv)
        file.decompress_bytes()
        logger.debug(f"Arquivo recebido do cliente {ctx.address}")
        return file

    def receive_message(self, client: socket.socket | ssl.SSLSocket, recv_bytes: int = 2048, block: bool = False) -> bytes:
        raw_msglen = client.recv(8)
        if not raw_msglen:
            return b""
        msglen = extract_message_length(self.decoder(raw_msglen))

        if block:
            message = client.recv(msglen)
            return self.pipeline.process_inbound(message)

        chunks = []
        bytes_received = 0
        while bytes_received < msglen:
            chunk = client.recv(recv_bytes)
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        return self.pipeline.process_inbound(b"".join(chunks))

    def send_message_udp(self, client_address, message: bytes, sent_bytes: int = 2048):
        self.hitory_udp_message.put((client_address, message))
        encoded = self.pipeline.process_outbound(message)
        self.server_socket.sendto(encoded, client_address)
        logger.debug(f"Mensagem UDP enviada para {client_address}: {encoded[:50]}...")

    def receive_message_udp(self, recv_bytes: int = 2048):
        try:
            data, address = self.server_socket.recvfrom(recv_bytes)
        except Exception as e:
            logger.error(f"Erro ao receber mensagem UDP: {e}")
            return b"", None

        if not data:
            return b"", address

        dec_message = self.pipeline.process_inbound(data)
        self.hitory_udp_message.put((address, dec_message))
        logger.debug(f"Mensagem UDP recebida de {address}: {dec_message[:50]}...")
        return dec_message, address

    def send_message_all_clients(self, message: bytes, sent_bytes: int = 2048):
        logger.info("Enviando mensagem para todos os clientes.")
        try:
            for ctx in self.__clients:
                self.send_message(ctx.connection, message, sent_bytes)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para todos os clientes: {e}")

    def send_message(self, client: socket.socket | ssl.SSLSocket, message: bytes, sent_bytes: int = 2048, block: bool = False) -> None:
        encoded = self.pipeline.process_outbound(message)
        msglen = len(encoded)
        try:
            client.sendall(self.encoder(struct.pack("!Q", msglen)))
        except Exception as e:
            logger.error(f"Erro ao enviar tamanho da mensagem: {e}")
            return

        if block:
            try:
                client.sendall(encoded)
                logger.debug(f"Mensagem bloqueada enviada: {encoded[:50]}...")
                return
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem bloqueada: {e}")

        offset = 0
        while offset < msglen:
            try:
                sent = client.send(encoded[offset:offset + sent_bytes])
                if not sent:
                    raise RuntimeError('Conexão interrompida')
                offset += sent
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                return
        logger.debug(f"Mensagem enviada: {encoded[:50]}...")

    def is_running(self) -> bool:
        return self.__running

    def get_clients(self) -> list[ThreadConnectionContext]:
        """Retorna a lista de contextos de conexão ativos."""
        return list(self.__clients)

    def save_clients(self, ctx: ThreadConnectionContext) -> None:
        if ctx not in self.__clients:
            self.__clients.append(ctx)
            logger.info(f"Cliente conectado: {ctx.address}, UUID: {ctx.uuid}")

    def sync_crypt_key(self, client: socket.socket | ssl.SSLSocket):
        try:
            client_public_key = self.decoder(client.recv(2048))
            client_public_key_obj = self.crypt.async_crypt.load_public_key(client_public_key)
            enc_key = self.crypt.async_crypt.encrypt_with_public_key(self.crypt.sync_crypt.get_key(), client_public_key_obj)
            client.sendall(self.encoder(enc_key))
            logger.debug(f"Chaves criptográficas sincronizadas com o cliente {client.getpeername() if hasattr(client, 'getpeername') else client}")
        except Exception as e:
            logger.error(f"Erro na sincronização de chaves: {e}")

    def break_server(self):
        logger.info("Servidor sendo interrompido...")
        self.__running = False
        for ctx in self.__clients:
            ctx.disconnect()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def get_client(self, uuid: str = "") -> ThreadConnectionContext | None:
        if not uuid and len(self.__clients) == 1:
            return self.__clients[0]
        for ctx in self.__clients:
            if ctx.uuid == uuid:
                return ctx
        return None

    def run(self) -> None:
        with socket.socket(*self.conn_type) as server_socket:
            self.server_socket = server_socket
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.HOST, self.PORT))

            if self.conn_type in [Types.TCP_IPV4, Types.TCP_IPV6]:
                server_socket.listen()
                logger.info("Servidor TCP rodando.")
                while self.__running:
                    try:
                        (client, address) = server_socket.accept()
                        logger.debug(f"Conexão TCP aceita de {address}")

                        if self.ssl_context:
                            try:
                                client = self.ssl_context.wrap_socket(client, server_side=True)
                                logger.debug(f"Conexão SSL/TLS estabelecida com {address}")
                            except Exception as ex:
                                logger.error(f"Erro ao envolver socket com SSL/TLS: {ex}")

                        ctx = ThreadConnectionContext(connection=client, address=address)

                        try:
                            if self.auth and not self.auth.validate_token(ctx):
                                ctx.disconnect()
                                logger.warning(f"Cliente {address} desconectado por falha na autenticação.")
                                continue
                        except Exception as e:
                            logger.error(f"Erro durante a autenticação do cliente {address}: {e}")

                        self.save_clients(ctx)

                    except KeyboardInterrupt:
                        logger.info("Servidor TCP interrompido por KeyboardInterrupt.")
                        self.break_server()
                        break
                    except Exception as e:
                        logger.error(f"Erro no servidor TCP: {e}")

            elif self.conn_type in [Types.UDP_IPV4, Types.UDP_IPV6]:
                logger.info("Servidor UDP rodando.")
                while self.__running:
                    try:
                        data, address = self.receive_message_udp()
                        if data:
                            self.hitory_udp_message.put(data)
                    except KeyboardInterrupt:
                        logger.info("Servidor UDP interrompido por KeyboardInterrupt.")
                        self.break_server()
                        break
                    except Exception as e:
                        logger.error(f"Erro no servidor UDP: {e}")
