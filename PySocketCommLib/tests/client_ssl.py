import socket
import ssl

# Configurações do cliente
HOST = 'localhost'
PORT = 12345
CERTFILE = './client.crt'  # Certificado do cliente
KEYFILE = './client.key'   # Chave privada do cliente
SERVER_CERTFILE = './server.crt'  # Certificado do servidor

# Cria um socket TCP/IP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Define o contexto SSL
context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
context.load_cert_chain(certfile=CERTFILE, keyfile=KEYFILE)
context.check_hostname = False

# Carrega manualmente o certificado do servidor
context.load_verify_locations(cafile=SERVER_CERTFILE)

# Conecta-se ao servidor
client_socket = context.wrap_socket(client_socket, server_hostname=HOST)
client_socket.connect((HOST, PORT))

# Envia dados para o servidor
message = 'Olá, servidor!'
client_socket.sendall(message.encode())

# Recebe a resposta do servidor
data = client_socket.recv(1024)
print(f'Mensagem recebida do servidor: {data.decode()}')

# Fecha a conexão
client_socket.close()
