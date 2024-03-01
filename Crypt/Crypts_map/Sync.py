from Crypt.Crypts.FernetCrypt import FernetCrypt
from Crypt.Crypts.AESCrypt import AESCrypt
from Abstracts.SyncCrypts import SyncCrypts

Sync: dict[str, type[SyncCrypts]] = {"fernet": FernetCrypt, "aes": AESCrypt}
