import socket
import threading
import struct
from Options.Ops import Client_ops
from Crypt.Crypt_main import Crypt

class Client(threading.Thread):
    def __init__(self, Options: Client_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST = Options.host
        self.PORT = Options.port
        self.BYTES = Options.bytes
        self.__running: bool = True
        self.connection = None
        if Options.encypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encypt_configs)
    
    def receive_message(self, sock: socket.socket):
        raw_msglen = sock.recv(1024)
        if not raw_msglen:
            return None
        msglen = int(raw_msglen.decode())
        chunks = []
        bytes_received = 0
        while bytes_received < msglen:
            chunk = sock.recv(min(msglen - bytes_received, 2048))
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)
            
        message = b" ".join(chunks)
        try:
            return self.crypt.sync_crypt.decrypt_message(message)
        except Exception as e:
            return message

    def send_message(self, sock: socket.socket, message: bytes):
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass
        msglen = len(message)
        sock.sendall(str(msglen).encode())
        offset = 0
        while offset < msglen:
            sent = sock.send(message[offset:offset+2048])
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
                self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connection.connect((self.HOST, self.PORT))
                self.sync_crypt_key(self.connection)
                return self.connection
            if not ignore_err:
                raise RuntimeError("Conexão já extabelecida")
        except Exception as e:
            print(e)

if __name__ == "__main__":
    client = Client()
    client.run()
