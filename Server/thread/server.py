import socket
import ssl
import struct
import threading
import sys
from Abstracts.Auth import Auth
from Events.Events import Events
from Options.Ops import Server_ops, Client_ops, SSLContextOps
from Crypt.crypt_main import Crypt
from Client.thread.client import Client
from Connection_type.Types import Types
from Files.File import File
from TaskManager.TaskManager import TaskManager
from Protocols.configure import config


class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.server_options = Options
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.auth: Auth = Options.auth
        self.conn_type: Types | tuple = Options.conn_type
        self.events = Events()
        self.taskManager = TaskManager()
        self.configureProtocol = config
        self.__clients: list[Client] = []
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

    def receive_message(self, client: socket.socket | ssl.SSLSocket, recv_bytes: int = 2048) -> bytes:
        raw_msglen = client.recv(8)
        if not raw_msglen:
            return b""
        msglen = struct.unpack("!Q", raw_msglen)[0]
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
            dec_message = self.crypt.sync_crypt.decrypt_message(message)
            if self.events.size() > 0:
                self.events.scam(dec_message)
            return dec_message
        except Exception as e:
            return message

    def send_message_all_clients(self, message: bytes, sent_bytes: int = 2048):
        try:
            for client in self.__clients:
                self.send_message(client.connection, message, sent_bytes)
        except Exception as e:
            print(e)

    def send_message(self, client: socket.socket | ssl.SSLSocket, message: bytes, sent_bytes: int = 2048) -> None:
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass
        msglen = len(message)
        client.sendall(struct.pack("!Q", msglen))
        offset = 0
        while offset < msglen:
            sent = client.send(message[offset:offset + sent_bytes])
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent

    def is_running(self) -> bool:
        return self.__running

    def save_clients(self, client: Client) -> None:
        if client not in self.__clients:
            self.__clients.append(client)

    def sync_crypt_key(self, client: socket.socket | ssl.SSLSocket):
        client_public_key = client.recv(2048)
        client_public_key_obj = self.crypt.async_crypt.load_public_key(client_public_key)
        enc_key = self.crypt.async_crypt.encrypt_with_public_key(self.crypt.sync_crypt.get_key(), client_public_key_obj)
        client.sendall(enc_key)

    def break_server(self):
        for client in self.__clients:
            client.disconnect()
        self.__running = False
        sys.exit(0)

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

                    try:
                        if self.crypt.async_crypt and self.crypt.sync_crypt:
                            self.sync_crypt_key(client)
                    except Exception as ex:
                        pass

                    cliente = Client(Client_ops(host=self.HOST, port=self.PORT, ssl_ops=self.server_options.ssl_ops,
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
                    print(e, 'caiu aqui')
                    sys.exit(1)


if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
