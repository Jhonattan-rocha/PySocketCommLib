import ssl
from Abstracts.Auth import Auth
from Connection_type.Types import Types
from typing import Callable, Any


class SyncCrypt_ops:
    def __init__(self, sync_crypt_select: str = "fernet", sync_key: bytes = b"") -> None:
        self.sync_crypt_select = sync_crypt_select
        self.sync_key = sync_key


class AsyncCrypt_ops:
    def __init__(self, async_crypt_select: str = "rsa", public_key=None, private_key=None) -> None:
        self.async_crypt_select = async_crypt_select
        self.public_key = public_key
        self.private_key = private_key


class Crypt_ops:
    def __init__(self, sync_crypt_ops: SyncCrypt_ops = None, async_crypt_ops: AsyncCrypt_ops = None) -> None:
        self.sync_crypt_ops = sync_crypt_ops
        self.async_crypt_ops = async_crypt_ops


class SSLContextOps:
    def __init__(self, ssl_context: ssl.SSLContext = None, SERVER_CERTFILE: str = "", CERTFILE: str = "",
                 KEYFILE: str = "", check_hostname: bool = True) -> None:
        self.ssl_context = ssl_context
        self.CERTFILE = CERTFILE
        self.KEYFILE = KEYFILE
        self.SERVER_CERTFILE = SERVER_CERTFILE
        self.check_hostname = check_hostname


class Server_ops:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, encrypt_configs: Crypt_ops = None,
                 conn_type: Types | tuple | None = Types.TCP_IPV4, ssl_ops: SSLContextOps = None,
                 auth: Auth = None, encoder: Callable[..., Any] = None, decoder: Callable[..., Any] = None) -> None:
        self.host = host
        self.port = port
        self.conn_type = conn_type
        self.ssl_ops = ssl_ops
        self.encrypt_configs = encrypt_configs
        self.auth = auth
        self.encoder = encoder
        self.decoder = decoder


class Client_ops:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080, encrypt_configs: Crypt_ops = None,
                 conn_type: Types | tuple | None = Types.TCP_IPV4, ssl_ops: SSLContextOps = None,
                 auth: Auth = None, encoder: Callable[..., Any] = None, decoder: Callable[..., Any] = None) -> None:
        self.host = host
        self.port = port
        self.conn_type = conn_type
        self.ssl_ops = ssl_ops
        self.encrypt_configs = encrypt_configs
        self.auth = auth
        self.encoder = encoder
        self.decoder = decoder
