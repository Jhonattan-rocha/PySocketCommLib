import socket
import threading
import sys
import struct
from Options.Ops import Server_ops
from Crypt.Crypt_main import Crypt

class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.__clients: list = []
        self.__running: bool = True
        if Options.encypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encypt_configs)
            
    def receive_message(self, sock: socket.socket) -> bytes:
        raw_msglen = sock.recv(4)
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

    def send_message(self, sock: socket.socket, message: bytes) -> None:
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
    
    def is_running(self) -> bool:
        return self.__running

    def save_clients(self, client) -> None:
        if client not in self.__clients:
            self.__clients.append(client)
    
    def sync_crypt_key(self, client: socket.socket):
        client_public_key = client.recv(2048)
        client_public_key_obj = self.crypt.async_crypt.load_public_key(client_public_key)
        enc_key = self.crypt.async_crypt.encrypt_with_public_key(self.crypt.sync_crypt.get_key(), client_public_key_obj)
        client.sendall(enc_key)

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

            server.bind((self.HOST, self.PORT))
            server.listen()
            
            print("Servidor rodando")
            while self.__running:
                try:
                    (client, address) = server.accept()
                    self.sync_crypt_key(client)
                    
                    print(f"Conexão com o cliente do address {address}")
                    
                    mes = self.receive_message(client)
                    
                    print(mes, self.crypt.sync_crypt.decrypt_message(mes))
                    
                    client.close()
                    
                    break
                except KeyboardInterrupt:
                    sys.exit(1)
                except Exception as e:
                    print(e)
                    sys.exit(1)

if __name__ == '__main__':
    server = Server(Options=Server_ops())
    server.start()
