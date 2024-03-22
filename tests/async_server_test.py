import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

import asyncio
from Server.Async.Server import Server
from Options.Ops import Server_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops, SSLContextOps

async def main():
    try:
        ssl = SSLContextOps(None, './server.crt', './server.crt', './server.key', False)
        
        server = Server(Server_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
        servidor_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(10)
        message = b'Mensagem do servidor'
        await server.send_message_all_clients(message)        
        
        await servidor_task
    except Exception as e:
        print(f"Erro na execução: {e}")
    
if __name__ == '__main__':
    asyncio.run(main())

