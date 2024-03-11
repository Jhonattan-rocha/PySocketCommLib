import time
from Client.Async.Client import Client
from Server.Async.Server import Server
from Options.Ops import Server_ops, Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops
import asyncio

def teste(x):
    print(f"{x}, esse print veio do evento")
    time.sleep(5)
    print(f"{x}, esse print veio do evento depois de 5 segundos")
async def main():
    try:
        client = Client(Client_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
        client.events.on("message", lambda x: teste(x))
        client_task = client.start()

        await client_task
    except Exception as e:
        print(f"Erro na execução: {e}")

if __name__ == "__main__":
    asyncio.run(main())