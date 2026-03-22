from ...Abstracts.SyncCrypts import SyncCrypts
from ...Options.Ops import SyncCrypt_ops
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from base64 import b64encode, b64decode
import os


class AESCrypt(SyncCrypts):
    """
    Criptografia AES no modo CFB (Cipher Feedback).

    CFB é um modo de stream cipher — não requer padding.
    A chave deve ter 16, 24 ou 32 bytes (AES-128, AES-192, AES-256).
    A chave é gerada com os.urandom para garantir entropia criptográfica.
    """

    def __init__(self, Options: SyncCrypt_ops) -> None:
        self.__key = b""
        if not Options.sync_key:
            self.generate_key(16)
        else:
            self.set_key(Options.sync_key)

    def encrypt_message(self, message: bytes) -> bytes:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.__key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(message) + encryptor.finalize()
        # Prefixo com IV para que o decrypt possa recuperá-lo
        return b64encode(iv + ciphertext)

    def decrypt_message(self, encrypted_blocks: bytes) -> bytes:
        data = b64decode(encrypted_blocks)
        iv = data[:16]
        ciphertext = data[16:]
        cipher = Cipher(algorithms.AES(self.__key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def generate_key(self, size: int) -> None:
        """Gera uma chave aleatória com entropia criptográfica (os.urandom)."""
        if size not in {16, 24, 32}:
            raise AttributeError("O tamanho da chave deve ser 16, 24 ou 32 bytes")
        self.__key = os.urandom(size)

    def get_key(self) -> bytes:
        return self.__key

    def set_key(self, key: bytes) -> None:
        if len(key) not in {16, 24, 32}:
            raise AttributeError("A chave deve ter 16, 24 ou 32 bytes")
        self.__key = key

