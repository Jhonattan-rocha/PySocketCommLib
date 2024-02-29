from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from Options.Ops import Crypy_ops
import socket


class Crypt:
    def __init__(self, Options: Crypy_ops) -> None:
        self.sync_key = Fernet.generate_key()
        self.sync_crypt = Fernet(self.sync_key)
        self.public_key = None
        self.private_key = None
    
    def load_public_key(self, public_key_bytes):
        public_key = serialization.load_pem_public_key(
            public_key_bytes,
            backend=default_backend()
        )
        return public_key
    
    def generate_key_pair(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        self.public_key = public_key
        self.private_key = private_key

    def encrypt_with_public_key(self, data, public_key):
        encrypted_data = public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return encrypted_data

    def decrypt_with_private_key(self, data, private_key):
        decrypted_data = private_key.decrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted_data

    def encrypt_message(self, message):
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
    
    def sync_crypt_key_server(self, client: socket.socket):
        if not self.public_key or not self.private_key:
            self.generate_key_pair()
        client_public_key = client.recv(2048)
        client_public_key_obj = self.load_public_key(client_public_key)
        enc_key = self.encrypt_with_public_key(self.sync_key, client_public_key_obj)
        client.sendall(enc_key)

    def sync_crypt_key_client(self, client: socket.socket):
        if not self.public_key or not self.private_key:
            self.generate_key_pair()
        client.sendall(self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
        sync_key = client.recv(2048)
        key = self.decrypt_with_private_key(sync_key, self.private_key)
        self.sync_key = Fernet(key)
