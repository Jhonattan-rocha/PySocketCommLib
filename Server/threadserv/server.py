import socket
import ssl
import struct
import threading
import sys
from queue import Queue
from Abstracts.Auth import Auth
from Auth.NoAuth import NoAuth
from Auth.SimpleAuth import SimpleTokenAuth
from Events import Events
from Options import Server_ops, Client_ops, SSLContextOps
from Crypt import Crypt
from Client import ThreadClient
from Connection_type.Types import Types
from Files import File
from TaskManager import TaskManager
from Protocols import config


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
        self.configureProtocol = config
        self.configureConnection = {}
        self.server_socket: socket.socket | None = None
        self.hitory_udp_message: Queue[tuple] = Queue(Options.MAX_HISTORY_UDP_MESSAGES)
        self.__clients: list[ThreadClient] = []
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

    def send_file(self, client: socket.socket | ssl.SSLSocket, file: File, bytes_block_length: int = 2048) -> None:
        """
        Sent file to client

        Args:
            client (socket.socket): client connection
            file (File): file opened with File class
            bytes_block_length (int, optional): block length for read. Defaults to 2048.
        """
        file.compress_file()
        self.send_message(client, b"".join([chunk for chunk in file.read(bytes_block_length)]), bytes_block_length)

    def receive_file(self, client: socket.socket | ssl.SSLSocket, bytes_block_length: int = 2048) -> File:
        """
        Receive file of client
            
        Args:
            client (socket.socket): client connection
            bytes_block_length (int, optional): block length for read. Defaults to 2048.

        Returns:
            File: Received file
        """
        file = File()
        bytes_recv = self.receive_message(client, bytes_block_length)
        file.setBytes(bytes_recv)
        file.decompress_bytes()
        return file
    
    def __extract_number(self, data):
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
    
    def receive_message(self, client: socket.socket | ssl.SSLSocket, recv_bytes: int = 2048, block: bool = False) -> bytes:
        raw_msglen = client.recv(8)
        if not raw_msglen:
            return b""
        msglen = self.__extract_number(self.decoder(raw_msglen))

        if block:
            message = client.recv(msglen)
            try:
                dec_message = self.crypt.sync_crypt.decrypt_message(self.decoder(message))
                if self.events.size() > 0:
                    self.events.scam(dec_message)
                return dec_message
            except Exception as e:
                return self.decoder(message)

        chunks = []
        bytes_received = 0
        while bytes_received < msglen:
            chunk = client.recv(recv_bytes)
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)

        message = b"".join(chunks)
        try:
            dec_message = self.crypt.sync_crypt.decrypt_message(self.decoder(message))
            if self.events.size() > 0:
                self.events.scam(dec_message)
            return dec_message
        except Exception as e:
            return self.decoder(message)
        
    def send_message_udp(self, client_address, message: bytes, sent_bytes: int = 2048):
        self.hitory_udp_message.put((client_address, message))
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass

        try:
            message = self.encoder(message.decode("cp850"))
        except Exception as e:
            pass

        self.server_socket.sendto(message.encode('cp850'), client_address)

    def receive_message_udp(self, recv_bytes: int = 2048):
        data, address = self.server_socket.recvfrom(recv_bytes)
        if not data:
            return b"", address

        try:
            dec_message = self.crypt.sync_crypt.decrypt_message(self.decoder(data))
            if self.events.size() > 0:
                self.events.scam(dec_message)
            return dec_message, address
        except Exception as e:
            return self.decoder(data), address

    def send_message_all_clients(self, message: bytes, sent_bytes: int = 2048):
        try:
            for client in self.__clients:
                self.send_message(client.connection, message, sent_bytes)
        except Exception as e:
            print(e)

    def send_message(self, client: socket.socket | ssl.SSLSocket, message: bytes, sent_bytes: int = 2048, block: bool = False) -> None:
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass

        try:
            message = self.encoder(message.decode("cp850"))
        except Exception as e:
            pass
        
        msglen = len(message)
        client.sendall(self.encoder(struct.pack("!Q", msglen).decode("cp850")))

        if block:
            client.sendall(message)
            return

        offset = 0
        while offset < msglen:
            sent = client.send(message[offset:offset + sent_bytes])
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent

    def is_running(self) -> bool:
        return self.__running

    def save_clients(self, client: ThreadClient) -> None:
        if client not in self.__clients:
            self.__clients.append(client)

    def sync_crypt_key(self, client: socket.socket | ssl.SSLSocket):
        client_public_key = self.decoder(client.recv(2048))
        client_public_key_obj = self.crypt.async_crypt.load_public_key(client_public_key)
        enc_key = self.crypt.async_crypt.encrypt_with_public_key(self.crypt.sync_crypt.get_key(), client_public_key_obj)
        client.sendall(self.encoder(enc_key))

    def break_server(self):
        for client in self.__clients:
            client.disconnect()
        self.__running = False
        sys.exit(0)
    
    def get_client(self, uuid: str = "") -> ThreadClient:
        if not uuid and len(self.__clients):
            return self.__clients.pop()
        for client in self.__clients:
            if str(client.uuid) == uuid:
                return client

    def run(self) -> None:
        with socket.socket(*self.conn_type) as server:

            server.bind((self.HOST, self.PORT))
            server.listen()

            print("Servidor rodando")
            while self.__running:
                try:
                    (client, address) = server.accept()

                    try:
                        client = self.ssl_context.wrap_socket(client, server_side=True)
                    except Exception as ex:
                        pass

                    cliente = ThreadClient(Client_ops(host=self.HOST, port=self.PORT, ssl_ops=self.server_options.ssl_ops,
                                                encrypt_configs=self.server_options.encrypt_configs,
                                                conn_type=self.conn_type))
                    cliente.connection = client

                    try:
                        if self.auth and not self.auth.validate_token(cliente):
                            cliente.disconnect()
                            continue
                    except Exception as e:
                        pass

                    self.save_clients(cliente)
                except KeyboardInterrupt:
                    sys.exit(1)
                except Exception as e:
                    sys.exit(1)

    def run(self) -> None:
        with socket.socket(*self.conn_type) as server_socket:
            self.server_socket = server_socket
            server_socket.bind((self.HOST, self.PORT))

            if self.conn_type in [Types.TCP_IPV4, Types.TCP_IPV6]:
                server_socket.listen()
                print("Servidor TCP rodando")
                while self.__running:
                    try:
                        (client, address) = server.accept()

                        try:
                            client = self.ssl_context.wrap_socket(client, server_side=True)
                        except Exception as ex:
                            pass

                        cliente = ThreadClient(Client_ops(host=self.HOST, port=self.PORT, ssl_ops=self.server_options.ssl_ops,
                                                    encrypt_configs=self.server_options.encrypt_configs,
                                                    conn_type=self.conn_type))
                        cliente.connection = client

                        try:
                            if self.auth and not self.auth.validate_token(cliente):
                                cliente.disconnect()
                                continue
                        except Exception as e:
                            pass

                        self.save_clients(cliente)
                    except KeyboardInterrupt:
                        sys.exit(1)
                    except Exception as e:
                        sys.exit(1)

            elif self.conn_type in [Types.UDP_IPV4, Types.UDP_IPV6]:
                print("Servidor UDP rodando")
                while self.__running:
                    try:
                        data = self.receive_message_udp()
                        if data:
                            self.hitory_udp_message.put(data)
                    except KeyboardInterrupt:
                        sys.exit(1)
                    except Exception as e:
                        print(f"Erro no servidor UDP: {e}")


if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
