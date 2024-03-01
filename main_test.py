from Crypt.crypt_main import Crypt
from Options.Ops import SyncCrypt_ops, AsyncCrypt_ops, Crypt_ops

texto = b"Nada a se fazeraaaaaaaaaaaaaaaaaaaaaa"

crypt = Crypt()
crypt.configure(Crypt_ops(async_crypt_ops=AsyncCrypt_ops("rsa")))

enc_texto = crypt.async_crypt.encrypt_with_public_key(texto)
dec_texto = crypt.async_crypt.decrypt_with_private_key(texto)

print(texto, enc_texto, dec_texto)
