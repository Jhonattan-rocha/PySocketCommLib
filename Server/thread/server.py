import socket
import struct
import threading
import sys
import re
from Events.Events import Events
from Options.Ops import Server_ops
from Crypt.Crypt_main import Crypt
from Client.Thread.Client import Client
from Connection_type.Types import Types
from Files.File import File
from TaskManager.TaskManager import TaskManager

class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.conn_type: Types|tuple = Options.conn_type
        self.events = Events()
        self.taskManager = TaskManager()
        self.__clients: list[list[type[Client], tuple]] = []
        self.__running: bool = True
        self.crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)
    
    def send_file(self, client: socket.socket, file: File, bytes_block_length: int=2048) -> None:
        file.compress_file()
        self.send_message(client, b"".join([chunk for chunk in file.read(bytes_block_length)]), bytes_block_length)
    
    def recive_file(self, client: socket.socket, bytes_block_length: int=2048) -> File:
        file = File()
        bytes_recv = self.receive_message(client, bytes_block_length)
        file.setBytes(bytes_recv)
        file.decompress_bytes()
        return file
    
    def receive_message(self, client: socket.socket, recv_bytes: int=2048) -> bytes:
        raw_msglen = client.recv(8)
        if not raw_msglen:
            return None
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

    def send_message(self, client: socket.socket, message: bytes, sent_bytes: int = 2048) -> None:
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

    def save_clients(self, client: list[list[type[Client], tuple]]) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
    
    def sync_crypt_key(self, client: socket.socket):
        client_public_key = client.recv(2048)
        client_public_key_obj = self.crypt.async_crypt.load_public_key(client_public_key)
        enc_key = self.crypt.async_crypt.encrypt_with_public_key(self.crypt.sync_crypt.get_key(), client_public_key_obj)
        client.sendall(enc_key)

    def run(self) -> None:
        with socket.socket(*self.conn_type) as server:

            server.bind((self.HOST, self.PORT))
            server.listen()
            
            print("Servidor rodando")
            while self.__running:
                try:
                    (client, address) = server.accept()
                    
                    try:
                        if self.crypt.async_crypt and self.crypt.sync_crypt:
                            self.sync_crypt_key(client)
                    except Exception as ex:
                        pass
                    
                    self.save_clients([client, address])
                    
                    self.send_message(client, b"!{message}:{Mensagem enviada do servidor}!")
                    
                    client.close()
                    break
                except KeyboardInterrupt:
                    sys.exit(1)
                except Exception as e:
                    print(e, 'Sever')
                    sys.exit(1)

if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
