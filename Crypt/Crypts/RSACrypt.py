from Abstracts.AsyncCrypts import AsyncCrypts
from Options.Ops import AsyncCrypt_ops
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

class RSACrypt(AsyncCrypts):
    def __init__(self, Options: AsyncCrypt_ops) -> None:
        self.public_key: rsa.RSAPublicKey = Options.public_key
        self.private_key: rsa.RSAPrivateKey = Options.private_key
        if not Options.public_key or not Options.private_key:
            self.generate_key_pair()
        
    def load_public_key(self, public_key_bytes: bytes):
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
    