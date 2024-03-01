from Abstracts.SyncCrypts import SyncCrypts
from Options.Ops import SyncCrypt_ops
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from base64 import b64encode, b64decode
import os
import string
import random

class AESCrypt(SyncCrypts):
    
    def __init__(self, Options: SyncCrypt_ops) -> None:
        self.key = Options.sync_key
        if not self.key:
            self.generate_key(16)
    
    def encrypt_message(self, message: bytes) -> bytes:
        # Gere um vetor de inicialização (IV) aleatório
        iv = os.urandom(16)

        # Padronize o texto antes da criptografia
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(message) + padder.finalize()

        # Crie um objeto de cifra AES com a chave e o modo CBC
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(iv), backend=default_backend())

        # Crie um objeto de contexto de cifra
        encryptor = cipher.encryptor()

        # Criptografe os dados
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Combine o IV e o texto cifrado e base64encode
        encrypted_message = b64encode(iv + ciphertext)
        
        return encrypted_message
    
    def decrypt_message(self, encrypted_blocks: bytes) -> bytes:
        # Decode a mensagem base64
        encrypted_blocks = b64decode(encrypted_blocks)

        # Extraia o IV da mensagem cifrada
        iv = encrypted_blocks[:16]

        # Crie um objeto de cifra AES com a chave e o modo CBC
        cipher = Cipher(algorithms.AES(self.key), modes.CFB(iv), backend=default_backend())

        # Crie um objeto de contexto de cifra
        decryptor = cipher.decryptor()

        # Descriptografe os dados
        decrypted_data = decryptor.update(encrypted_blocks[16:]) + decryptor.finalize()

        # Remova o preenchimento
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(decrypted_data) + unpadder.finalize()

        return plaintext

    def generate_key(self, size: int) -> None:
        text = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.hexdigits
        key = "".join(random.choice(text) for _ in range(size))
        self.key = key.encode()
        