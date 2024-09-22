import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

import time
from Server.Thread.server import Server
from Options.Ops import Server_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops

def main():
    try:
        server = Server(Server_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('fernet'), AsyncCrypt_ops("rsa"))))
        server.start()
        print("Server rodando.")
        time.sleep(10)
        server.send_message_all_clients(b'Mensagem do servidor')        
    except Exception as e:
        print(f"Erro na execução: {e}")
    
main()
