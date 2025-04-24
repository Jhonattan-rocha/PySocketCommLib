from Crypt.Crypts.RSACrypt import RSACrypt
from Abstracts.AsyncCrypts import AsyncCrypts

Async: dict[str, type[AsyncCrypts]] = {"rsa": RSACrypt}
