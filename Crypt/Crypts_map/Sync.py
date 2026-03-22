from .. import FernetCrypt
from .. import AESCrypt
from ...Abstracts.SyncCrypts import SyncCrypts

Sync: dict[str, type[SyncCrypts]] = {"fernet": FernetCrypt, "aes": AESCrypt}
