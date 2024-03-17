from Client.Async.Client import Client
from Server.Async.Server import Server
from Options.Ops import Server_ops, Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops
import asyncio

async def main():
    try:
        server = Server(Server_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
        server_task = server.start()
                
        await server_task        
    except Exception as e:
        print(f"Erro na execução: {e}")

if __name__ == "__main__":
    asyncio.run(main())