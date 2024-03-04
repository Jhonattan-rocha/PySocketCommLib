import re
import socket
import struct
import threading
from Files.File import File
from Options.Ops import Client_ops
from Crypt.Crypt_main import Crypt
from Connection_type.Types import Types

class Client(threading.Thread):
    def __init__(self, Options: Client_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST = Options.host
        self.PORT = Options.port
        self.BYTES = Options.bytes
        self.__running: bool = True
        self.connection = None
        self.conn_type: Types|tuple = Options.conn_type
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
            return self.crypt.sync_crypt.decrypt_message(message)
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
    
    def sync_crypt_key(self, client: socket.socket):
        client.sendall(self.crypt.async_crypt.public_key_to_bytes())
        enc_key = client.recv(2048)
        key = self.crypt.async_crypt.decrypt_with_private_key(enc_key)
        self.crypt.sync_crypt.set_key(key)
    
    def is_running(self) -> bool:
        return self.__running
    
    def connect(self, ignore_err=False) -> socket.socket:
        try:
            if not self.connection:
                self.connection = socket.socket(*self.conn_type)
                self.connection.connect((self.HOST, self.PORT))
                try:
                    if self.crypt.async_crypt and self.crypt.sync_crypt:
                        self.sync_crypt_key(self.connection)
                except Exception as ex:
                    pass
                
                file = File(r"C:\Users\Jhinattan Rocha\Documents\Documentos meus\VID_20211102_150812642.mp4", "rb")
                file.open()
                self.send_file(self.connection, file, 4*1024*1024)               
                return self.connection
            if not ignore_err:
                raise RuntimeError("Conexão já extabelecida")
        except Exception as e:
            print(e)
    
    def run(self) -> None:
        self.connect(False)
            
if __name__ == "__main__":
    client = Client()
    client.run()
