class Crypy_ops:
    def __init__(self, sync_crypt: str="fernet", async_crypt: str="rsa", public_key=None, private_key=None) -> None:
        self.sync_crypt = sync_crypt
        self.async_crypt = async_crypt
        self.public_key = public_key
        self.private_key = private_key
        
class Server_ops:
    def __init__(self, host: str="127.0.0.1", port: int=8080, bytes: bytes=2048, enable_crypt: bool=True) -> None:    
        self.host = host
        self.port = port
        self.bytes = bytes
        self.enable_crypt = enable_crypt

class Client_ops:
    def __init__(self, host: str="127.0.0.1", port: int=8080, bytes: bytes=2048, enable_crypt: bool=True) -> None:    
        self.host = host
        self.port = port
        self.bytes = bytes
        self.enable_crypt = enable_crypt
