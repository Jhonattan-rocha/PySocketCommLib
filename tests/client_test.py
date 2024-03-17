import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

from Client.Thread.Client import Client
from Options.Ops import Client_ops, Crypt_ops, SyncCrypt_ops, AsyncCrypt_ops

def main():
    try:
        client = Client(Client_ops(encrypt_configs=Crypt_ops(SyncCrypt_ops('aes'), AsyncCrypt_ops("rsa"))))
        client.connect(True)
        print(client.receive_message())
    except Exception as e:
        print(f"Erro na execução: {e}")

main()
