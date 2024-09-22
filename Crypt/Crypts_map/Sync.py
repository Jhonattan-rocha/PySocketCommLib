from Crypt import FernetCrypt
from Crypt import AESCrypt
from Abstracts import SyncCrypts

Sync: dict[str, type[SyncCrypts]] = {"fernet": FernetCrypt, "aes": AESCrypt}
