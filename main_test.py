from Options.Ops import SyncCrypt_ops, Crypt_ops
from Crypt.Crypt_main import Crypt

texto = b"Nada a se fazer"
print(texto)

crypt = Crypt() 
crypt.configure(Crypt_ops(sync_crypt_ops=SyncCrypt_ops("aes")))

enc = crypt.sync_crypt.encrypt_message(texto)
print(enc)

dec = crypt.sync_crypt.decrypt_message(enc)
print(dec)
