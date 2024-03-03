import re
import socket
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
    
    def send_file(self, file: File, client: socket.socket) -> None:
        lenght = file.size()
        
        self.send_message(client, re.sub(r"\D+", "", str(lenght)).encode())
        
        for chunk in file.read(2048):
            if not chunk:
                break
            self.send_message(client, chunk)
    
    def recive_file(self, client: socket.socket) -> File:
        lenght = self.receive_message(client)
        lenght = int(re.sub(r"\D+", "", lenght.decode()))
        
        chunks = b""
        bytes_rec = 0
        while bytes_rec < lenght:
            chunk = self.receive_message(client)
            if not chunk:
                break
            chunks += chunk
            bytes_rec += len(chunk)
        
        file = File()
        file.setFile(chunks)
        return file
    
    def receive_message(self, client: socket.socket):
        raw_msglen = client.recv(4)
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
                
                file = File(r"C:\Users\Jhinattan Rocha\Pictures\nada.jpeg", 'rb')
                file.open()
                self.send_file(file, self.connection)
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
