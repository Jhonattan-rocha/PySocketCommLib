import re
import socket
import threading
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
    
    def receive_message(self, client: socket.socket):
        raw_msglen = client.recv(1024)
        if not raw_msglen:
            return None
        msglen = int(re.sub(r"\D+", "", raw_msglen.decode()))
        chunks = []
        bytes_received = 0
        while bytes_received < msglen:
            chunk = client.recv(min(msglen - bytes_received, 2048))
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)
            
        message = b" ".join(chunks)
        try:
            return self.crypt.sync_crypt.decrypt_message(message)
        except Exception as e:
            return message

    def send_message(self, client: socket.socket, message: bytes):
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass
        msglen = len(message)
        client.sendall(str(msglen).encode())
        offset = 0
        while offset < msglen:
            sent = client.send(message[offset:offset+2048])
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
                
                self.send_message(self.connection, b"Hellow world")
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
