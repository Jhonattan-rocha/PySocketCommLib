import asyncio
from concurrent.futures import ThreadPoolExecutor
from Abstracts.SyncCrypts import SyncCrypts
from Options.Ops import SyncCrypt_ops
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from base64 import b64encode, b64decode
from typing import Callable, Any
import os
import string
import random


class AESCrypt(SyncCrypts):

    def __init__(self, Options: SyncCrypt_ops) -> None:
        self.__key = b""
        self.__padding = 0
        if not Options.sync_key:
            self.generate_key(16)
        else:
            key_len = len(Options.sync_key)
            if key_len != 16 and key_len != 24 and key_len != 32:
                raise AttributeError("A chave só pode ter 16, 24 e 32 byes")
            self.set_key(Options.sync_key)

    def encrypt_message(self, message: bytes) -> bytes:
        # Gere um vetor de inicialização (IV) aleatório
        iv = os.urandom(16)

        # Padronize o texto antes da criptografia
        padder = padding.PKCS7(self.__padding).padder()
        padded_data = padder.update(message) + padder.finalize()

        # Crie um objeto de cifra AES com a chave e o modo CBC
        cipher = Cipher(algorithms.AES(self.__key), modes.CFB(iv), backend=default_backend())

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
        cipher = Cipher(algorithms.AES(self.__key), modes.CFB(iv), backend=default_backend())

        # Crie um objeto de contexto de cifra
        decryptor = cipher.decryptor()

        # Descriptografe os dados
        decrypted_data = decryptor.update(encrypted_blocks[16:]) + decryptor.finalize()

        # Remova o preenchimento
        unpadder = padding.PKCS7(self.__padding).unpadder()
        plaintext = unpadder.update(decrypted_data) + unpadder.finalize()

        return plaintext

    def generate_key(self, size: int) -> None:
        text = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.hexdigits
        key = "".join(random.choice(text) for _ in range(size))
        self.set_key(key.encode())

    def get_key(self) -> bytes:
        return self.__key

    def set_key(self, key: bytes) -> None:
        key_len = len(key)
        if key_len not in {16, 24, 32}:
            raise AttributeError("A chave só pode ter 16, 24 e 32 bytes")

        self.__key = key
        self.__padding = key_len * 8

    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res
