class SyncCrypt_ops:
    def __init__(self, sync_crypt: str="fernet", sync_key: bytes=b"") -> None:
        self.sync_crypt = sync_crypt
        self.sync_key = sync_key

class AsyncCrypt_ops:
    def __init__(self, async_crypt: str="rsa", public_key=None, private_key=None) -> None:
        self.async_crypt = async_crypt
        self.public_key = public_key
        self.private_key = private_key
        
class Crypt_ops:
    def __init__(self, enable_sync_crypt: bool, enable_async_crypt: bool, sync_crypt_ops: SyncCrypt_ops, async_crypt_ops: AsyncCrypt_ops) -> None:
        self.enable_sync_crypt = enable_sync_crypt
        self.enable_async_crypt = enable_async_crypt
        
        self.sync_crypt_ops = sync_crypt_ops
        
        self.async_crypt_ops = async_crypt_ops
        
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
