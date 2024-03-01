from Abstracts.SyncCrypts import SyncCrypts
from Options.Ops import SyncCrypt_ops
from cryptography.fernet import Fernet

class FernetCrypt(SyncCrypts):
    def __init__(self, Options: SyncCrypt_ops) -> None:
        self.sync_key: bytes = Options.sync_key if Options.sync_key else Fernet.generate_key()
        try:
            self.sync_crypt = Fernet(self.sync_key)
        except Exception as e:
            self.sync_key = Fernet.generate_key()
            self.sync_crypt = Fernet(self.sync_key)
            print(f"Devido ao erro: {e}, foi gerado uma nova chave")
        
    def encrypt_message(self, message: bytes):
        try:
            return self.sync_crypt.encrypt(message)
        except Exception as e:
            print(e)
            return b""

    def decrypt_message(self, encrypted_blocks: bytes):
        try:
            return self.sync_crypt.decrypt(encrypted_blocks)
        except Exception as e:
            print(e)
            return b""