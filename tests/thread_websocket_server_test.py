import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

import time
from Server.Thread.server import Server
from Options.Ops import Server_ops

def main():
    try:
        server = Server(Server_ops())
        web_socket_server = server.configureProtocol("websocket_server")()
        server.start()

        time.sleep(10)
        
        client = server.get_client()
        web_socket_server.handshake(client.connection)

        while True:
            message = client.connection.recv(1024)
            if not message:
                break
            print(f"Mensagem recebida: {web_socket_server.decode_message(message)}")
            client.connection.send(web_socket_server.encode_message("Mensagem recebida com sucesso"))
            
    except Exception as e:
        print(f"Erro na execução: {e}")
    
main()
