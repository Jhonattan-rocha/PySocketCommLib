import socket
import ssl
import struct
import threading
import uuid
from queue import Queue
from Abstracts.Auth import Auth
from Events import Events
from Files import File
from Options import Client_ops, SSLContextOps
from Crypt import Crypt
from Connection_type import Types
from TaskManager import TaskManager
from Protocols import config


class Client(threading.Thread):
    def __init__(self, Options: Client_ops) -> None:
        threading.Thread.__init__(self)
        self.client_options = Options
        self.HOST = Options.host
        self.PORT = Options.port
        self.encoder = Options.encoder
        self.decoder = Options.decoder
        self.auth: Auth = Options.auth
        self.uuid = uuid.uuid4()
        self.events = Events()
        self.taskManager = TaskManager()
        self.configureProtocol = config
        self.configureConnection = {}
        self.history_udp_messages: Queue[tuple] = Queue()
        self.__running: bool = True
        self.connection: socket.socket | ssl.SSLSocket | None = None
        self.conn_type: Types | tuple = Options.conn_type
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

    def send_file(self, file: File, bytes_block_length: int = 2048) -> None:
        file.compress_file()
        self.send_message(b"".join([chunk for chunk in file.read(bytes_block_length)]), bytes_block_length)

    def receive_file(self, bytes_block_length: int = 2048) -> File:
        file = File()
        bytes_recv = self.receive_message(bytes_block_length)
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

    def receive_message(self, recv_bytes: int = 2048, block: bool = False) -> bytes:
        raw_msglen = self.connection.recv(8)
        if not raw_msglen:
            return b""
        msglen = self.__extract_number(self.decoder(raw_msglen))

        if block:
            message = self.connection.recv(msglen)
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
            chunk = self.connection.recv(recv_bytes)
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
        self.history_udp_messages.put((client_address, message))
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass

        try:
            message = self.encoder(message.decode("cp850"))
        except Exception as e:
            pass

        self.connection.sendto(message.encode('cp850'), client_address)

    def receive_message_udp(self, recv_bytes: int = 2048):
        data, address = self.connection.recvfrom(recv_bytes)
        if not data:
            return b"", address

        try:
            dec_message = self.crypt.sync_crypt.decrypt_message(self.decoder(data))
            if self.events.size() > 0:
                self.events.scam(dec_message)
            self.history_udp_messages.put((address, dec_message)) 
            return dec_message, address
        except Exception as e:
            return self.decoder(data), address

    def send_message(self, message: bytes, sent_bytes: int = 2048, block: bool = False) -> None:
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass

        try:
            message = self.encoder(message)
        except Exception as e:
            pass
        
        msglen = len(message)
        self.connection.sendall(self.encoder(struct.pack("!Q", msglen)))

        if block:
            self.connection.sendall(message)
            return

        offset = 0
        while offset < msglen:
            sent = self.connection.send(message[offset:offset + sent_bytes])
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent

    def sync_crypt_key(self):
        self.connection.sendall(self.encoder(self.crypt.async_crypt.public_key_to_bytes()))
        enc_key = self.decoder(self.connection.recv(2048))
        key = self.crypt.async_crypt.decrypt_with_private_key(enc_key)
        self.crypt.sync_crypt.set_key(key)

    def is_running(self) -> bool:
        return self.__running

    def disconnect(self) -> None:
        self.connection.close()
        self.__running = False   

    def connect(self, ignore_err=False) -> None:
        try:
            if not self.connection:
                self.connection = socket.socket(*self.conn_type)

                if self.conn_type in [Types.TCP_IPV4, Types.TCP_IPV6]:
                    try:
                        self.connection = self.ssl_context.wrap_socket(self.connection, server_hostname=self.HOST)
                    except Exception as e:
                        pass 

                    self.connection.connect((self.HOST, self.PORT))

                    try:
                        if self.auth and not self.auth.validate_token(self):
                            self.disconnect()
                            return 
                    except Exception as e:
                        pass

                elif self.conn_type in [Types.UDP_IPV4, Types.UDP_IPV6]: 
                    pass

                self.__running = True
            if not ignore_err:
                raise RuntimeError("Conexão já estabelecida")
        except Exception as e:
            self.__running = False
            print(e)


if __name__ == "__main__":
    client = Client()
    client.connect(False)
