import sys
import threading
from Crypt.Crypt_main import Crypt
from Events.Events import Events
from Files.File import File
from Options.Ops import Server_ops
from TaskManager.TaskManager import TaskManager
import socketio

class Server(threading.Thread):
    
    def __init__(self, Options: Server_ops) -> None:
        threading.Thread.__init__(self)
        self.HOST: str = Options.host
        self.PORT: int = Options.port
        self.events = Events()
        self.taskManager = TaskManager()
        self.sio = socketio.Server()
        self.__recv_bytes: dict[int, tuple] = []
        self.__clients: list[tuple] = []
        self.__running: bool = True
        self.crypt = None
        if Options.encrypt_configs:
            self.crypt = Crypt()
            self.crypt.configure(Options.encrypt_configs)
    
    def send_file(self, sid: int, file: File, bytes_block_length: int=2048) -> None:
        pass
    
    def recive_file(self, sid: int, bytes_block_length: int=2048) -> File:
        pass
    
    def receive_message(self, sid: int, data: bytes, room=None) -> bytes:
        dec_message = b''
        try:
            dec_message = self.crypt.sync_crypt.decrypt_message(data)
            if self.events.size() > 0:
                self.events.scam(dec_message)
            return dec_message
        except Exception as e:
            dec_message = data
        
        if dec_message == r'\\b':
            self.send_message(room, self.__recv_bytes[sid], 4*1024*1024)
            del self.__recv_bytes[sid]
        
        self.__recv_bytes[sid] = self.__recv_bytes[sid] + dec_message 
            
    def send_message(self, sid: int, message: bytes, sent_bytes: int = 2048) -> None:
        try:
            message = self.crypt.sync_crypt.encrypt_message(message)
        except Exception as e:
            pass
        msglen = len(message)
        offset = 0
        while offset < msglen:
            sent = self.sio.emit('message', message[offset:offset + sent_bytes], room=sid)
            if not sent:
                raise RuntimeError('Conexão interrompida')
            offset += sent
    
    def is_running(self) -> bool:
        pass
    
    def save_clients(self, client: tuple) -> None:
        pass
    
    def sync_crypt_key(self, sid: int):
        pass
    
    def break_server(self):
        sys.exit(0)
    
    def run(self) -> None:
        app = socketio.WSGIApp(self.sio)
        socketio.run(app, port=self.PORT)
    