import socket
import threading
import sys
import struct
from Options.Ops import Server_ops
from Crypt.crypt_main import Crypt

class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.__clients: list = []
        self.__running: bool = True
        if Options.enable_crypt:
            self.crypt = Crypt()
    
    def receive_message(self, sock: socket.socket) -> bytes:
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

    def send_message(self, sock: socket.socket, message: bytes) -> None:
        msglen = len(message)
        sock.sendall(struct.pack('>I', msglen))
        offset = 0
        while offset < msglen:
            sent = sock.send(message[offset:offset+2048])
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent
    
    def is_running(self) -> bool:
        return self.__running

    def save_clients(self, client) -> None:
        if client not in self.__clients:
            self.__clients.append(client)

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

            server.bind((self.HOST, self.PORT))
            server.listen()
            
            print("Servidor rodando")
            while self.__running:
                try:
                    (client, address) = server.accept()
                
                    print(f"Conexão com o cliente do address {address}")

                except KeyboardInterrupt:
                    sys.exit(1)
                except Exception as e:
                    print(e)
                    sys.exit(1)

if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
