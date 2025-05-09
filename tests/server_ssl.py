import socket
import ssl

# Configurações do servidor
HOST = 'localhost'
PORT = 12345
CERTFILE = './server.crt'  # Certificado do servidor
KEYFILE = './server.key'   # Chave privada do servidor

# Cria um socket TCP/IP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Define o contexto SSL
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.check_hostname = False
context.load_cert_chain(certfile=CERTFILE, keyfile=KEYFILE)

# Liga o socket ao endereço e porta especificados
server_socket.bind((HOST, PORT))

# Escuta por conexões entrantes
server_socket.listen(1)

print(f'Servidor ouvindo em {HOST}:{PORT}...')

while True:
    # Espera por uma nova conexão
    conn, addr = server_socket.accept()
    conn = context.wrap_socket(conn, server_side=True)

    print(f'Conexão estabelecida com {addr}')

    # Recebe dados do cliente
    data = conn.recv(1024)
    if not data:
        break

    print(f'Mensagem recebida do cliente: {data.decode()}')

    # Envia uma resposta de volta ao cliente
    conn.sendall('Mensagem recebida no servidor'.encode())

# Fecha a conexão
conn.close()
