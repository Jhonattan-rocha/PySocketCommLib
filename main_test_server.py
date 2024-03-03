from Client.Thread.Client import Client
from Server.Thread.Server import Server
from Options.Ops import Server_ops, Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops

server = Server(Server_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
server_task = server.start()
        