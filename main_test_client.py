from Client.Thread.Client import Client
from Server.Thread.Server import Server
from Options.Ops import Server_ops, Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops
import asyncio

def main():
    try:
        client = Client(Client_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
        client_task = client.start()

    except Exception as e:
        print(f"Erro na execução: {e}")

if __name__ == "__main__":
    main()