from Crypt import FernetCrypt
from Crypt import AESCrypt
from Abstracts.SyncCrypts import SyncCrypts

Sync: dict[str, type[SyncCrypts]] = {"fernet": FernetCrypt, "aes": AESCrypt}
