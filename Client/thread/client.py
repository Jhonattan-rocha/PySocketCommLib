import socket
import threading
import struct
from Options.Ops import Client_ops
from Crypt.crypt_main import Crypt

class Client(threading.Thread):
    def __init__(self, Options: Client_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST = Options.host
        self.PORT = Options.port
        self.BYTES = Options.bytes
        self.__running: bool = True
        if Options.enable_crypt:
            self.crypt = Crypt()
    
    def receive_message(self, sock: socket.socket):
        raw_msglen = sock.recv(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        chunks = []
        bytes_received = 0
        while bytes_received < msglen:
            chunk = sock.recv(min(msglen - bytes_received, 2048))
            if not chunk:
                raise RuntimeError('Conexão interrompida')
            chunks.append(chunk)
            bytes_received += len(chunk)
        return b" ".join(chunks)

    def send_message(self, sock, message):
        msglen = len(message)
        sock.sendall(struct.pack('>I', msglen))
        offset = 0
        while offset < msglen:
            sent = sock.send(message[offset:offset+2048])
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent
    
    def connect(self) -> socket.socket:
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((self.HOST, self.PORT))
            return self.connection
        except Exception as e:
            print(e)

if __name__ == "__main__":
    client = Client()
    client.run()
