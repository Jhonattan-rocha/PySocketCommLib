import socket
import struct
import threading
import sys
import re
from Options.Ops import Server_ops
from Crypt.Crypt_main import Crypt
from Client.Thread.Client import Client
from Connection_type.Types import Types
from Files.File import File

class Server(threading.Thread):
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.BYTES: bytes = Options.bytes
        self.conn_type: Types|tuple = Options.conn_type
        self.__clients: list[str, type[list[type[tuple], type[Client]]]] = []
        self.__running: bool = True
        self.crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)
        
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
                    
                    print(f"Conexão com o cliente do address {address}")
                    
                    bytes_file = self.receive_message(client, 4*1024*1024)
                    file = File()
                    file.set_full_path("./teste.mp4")
                    print(len(bytes_file))
                    file.setFile(bytes_file)
                    file.save()
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
