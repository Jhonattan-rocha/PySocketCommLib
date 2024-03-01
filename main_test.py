from Crypt.crypt_main import Crypt
from Options.Ops import SyncCrypt_ops, Crypt_ops

texto = b"Nada a se fazer"

crypt = Crypt()
crypt.configure(Crypt_ops(sync_crypt_ops=SyncCrypt_ops("fernet")))

enc_texto = crypt.sync_crypt.encrypt_message(texto)
dec_texto = crypt.sync_crypt.decrypt_message(enc_texto)

print(texto, enc_texto, dec_texto)
