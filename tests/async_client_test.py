import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

from Client.Async.Client import Client
from Options.Ops import Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops, SSLContextOps
import asyncio

async def main():
    try:
        ssl = SSLContextOps(None, './server.crt', './client.crt', './client.key', False)
        client = Client(Client_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa")), ssl_ops=ssl))
        client_task = asyncio.create_task(client.start())
        
        await client_task
        
        print(await client.receive_message())
    except Exception as e:
        print(f"Erro na execução: {e}")

if __name__ == '__main__':
    asyncio.run(main())
