from Options import Crypt_ops
from Crypt import Sync
from Crypt import Async


class Crypt:
    def __init__(self):
        self.async_crypt = None
        self.sync_crypt = None

    def configure(self, Options: Crypt_ops):
        try:
            if Options.sync_crypt_ops:
                self.sync_crypt = Sync[str(Options.sync_crypt_ops.sync_crypt_select).lower()](Options.sync_crypt_ops)
            if Options.async_crypt_ops:
                self.async_crypt = Async[str(Options.async_crypt_ops.async_crypt_select).lower()](
                    Options.async_crypt_ops)
        except Exception as e:
            raise TypeError("Criptografia não encontrada ou não mapeada")
