import socket
import struct
import sys
import hashlib
import hmac
import base64
import os

def criar_conexao_postgres(host, port, usuario, banco_de_dados, senha):
    """
    Cria uma conexão PostgreSQL usando sockets diretamente.
    (Código com tratamento de erros melhorado e comentários adicionais)
    """
    sock = None # Inicializar sock fora do try para poder fechar no finally
    try:
        # 1. Criar Socket TCP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"Conectado a {host}:{port}")

        # 2. Enviar Mensagem de Startup
        startup_message = construir_mensagem_startup(usuario, banco_de_dados)
        sock.sendall(startup_message)
        print("Mensagem de Startup enviada.")

        # 3. Lidar com a Autenticação
        if not lidar_autenticacao(sock, usuario, senha):
            print("Falha na autenticação.")
            encerrar_conexao(sock) # Usar função para encerrar conexão explicitamente
            return None
        print("Autenticação bem-sucedida.")

        return sock

    except socket.error as e:
        print(f"Erro de socket ao conectar a {host}:{port}: {e}", file=sys.stderr) # Imprimir erro para stderr
        return None
    except Exception as e:
        print(f"Erro inesperado ao criar conexão: {e}", file=sys.stderr) # Imprimir erro para stderr
        return None
    finally:
        if not sock: # Se a conexão não foi estabelecida, garantir que o socket (se criado) seja fechado
            if sock:
                encerrar_conexao(sock)

def encerrar_conexao(sock):
    """
    Encerra a conexão de socket de forma segura.
    """
    if sock:
        try:
            sock.shutdown(socket.SHUT_RDWR) # Desligar envio e recebimento
            sock.close()
            print("Conexão encerrada.")
        except socket.error as e:
            print(f"Erro ao encerrar conexão: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Erro inesperado ao encerrar conexão: {e}", file=sys.stderr)


def construir_mensagem_startup(usuario, banco_de_dados):
    """
    Constrói a mensagem de Startup para o PostgreSQL.
    """
    parametros = {
        'user': usuario,
        'database': banco_de_dados
    }

    parametros_str = ""
    for chave, valor in parametros.items():
        parametros_str += chave + '\0' + valor + '\0'
    parametros_str += '\0' # Finalizador da lista de parâmetros

    mensagem_corpo = struct.pack('!i', 196608) + parametros_str.encode('utf-8') # 196608 = Versão 3.0 do protocolo
    tamanho_mensagem = len(mensagem_corpo) + 4 # Tamanho total inclui o tamanho em si (4 bytes)
    mensagem_completa = struct.pack('!i', tamanho_mensagem) + mensagem_corpo
    return mensagem_completa

def lidar_autenticacao(sock, usuario, senha):
    """
    Lida com o processo de autenticação, incluindo MD5 e SCRAM-SHA-256.
    """
    try:
        while True:
            tipo_mensagem = sock.recv(1)
            if not tipo_mensagem:
                print("Conexão fechada pelo servidor inesperadamente.", file=sys.stderr)
                return False

            tipo_mensagem_int = ord(tipo_mensagem)

            tamanho_mensagem_bytes = sock.recv(4)
            if len(tamanho_mensagem_bytes) < 4:
                print("Conexão fechada durante leitura do tamanho.", file=sys.stderr)
                return False

            tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
            corpo_mensagem = b''
            while len(corpo_mensagem) < tamanho_mensagem:
                parte = sock.recv(tamanho_mensagem - len(corpo_mensagem))
                if not parte:
                    break
                corpo_mensagem += parte

            if tipo_mensagem_int == ord('E'):  # Error message
                erro_msg = corpo_mensagem.decode('utf-8', errors='ignore')
                print(f"Erro do Servidor: {erro_msg}", file=sys.stderr)
                return False
            elif tipo_mensagem_int == ord('R'):  # Authentication Request
                tipo_autenticacao = struct.unpack('!i', corpo_mensagem[:4])[0]
                if tipo_autenticacao == 5:  # MD5 Password
                    salt = corpo_mensagem[4:8]
                    print(f"Servidor solicitou autenticação MD5 (salt: {salt.hex()})")
                    hash_md5 = calcular_md5(usuario, senha, salt)
                    mensagem_senha = construir_mensagem_senha(hash_md5)
                    sock.sendall(mensagem_senha)
                elif tipo_autenticacao == 10:  # SASL Authentication
                    mecanismos_sasl = corpo_mensagem[4:].split(b'\x00')
                    if b'SCRAM-SHA-256' in mecanismos_sasl:
                        print("Servidor suporta SCRAM-SHA-256. Iniciando autenticação SCRAM.")
                        if not lidar_autenticacao_scram_sha_256(sock, usuario, senha):
                            return False
                    else:
                        print(f"SCRAM-SHA-256 não suportado pelo servidor. Mecanismos suportados: {mecanismos_sasl}", file=sys.stderr)
                        return False
                elif tipo_autenticacao == 0:  # Authentication OK
                    print("Autenticação bem-sucedida!")
                    return True
                else:
                    print(f"Método de autenticação não suportado: {tipo_autenticacao}", file=sys.stderr)
                    return False
            elif tipo_mensagem_int == ord('S'):  # ParameterStatus
                pass  # Ignorar
            else:
                print(f"Tipo de mensagem desconhecido: {tipo_mensagem_int}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"Erro durante autenticação: {str(e)}", file=sys.stderr)
        return False

# Funções MD5 (já existentes - mantenha para compatibilidade ou remova se focar apenas em SCRAM)
def calcular_md5(usuario, senha, salt):
    import hashlib
    temp_hash = hashlib.md5(senha.encode('utf-8') + usuario.encode('utf-8')).hexdigest().encode('utf-8')
    final_hash = hashlib.md5(temp_hash + salt).hexdigest()
    return f"md5{final_hash}"

def construir_mensagem_senha(senha_hash):
    senha_com_terminador = senha_hash.encode('utf-8') + b'\x00'
    tamanho = len(senha_com_terminador) + 4
    return b'p' + struct.pack('!i', tamanho) + senha_com_terminador

# ------------------- Funções SCRAM-SHA-256 -------------------
def lidar_autenticacao_scram_sha_256(sock, usuario, senha):
    """
    Lida com o processo de autenticação SCRAM-SHA-256.
    """
    try:
        # 1. Enviar SASLInitialResponse (Client First Message)
        client_nonce = gerar_nonce()
        client_first_message = construir_client_first_message(usuario, client_nonce)
        mensagem_inicial_sasl = construir_mensagem_inicial_sasl(client_first_message)
        print(f"Mensagem SASL inicial (codificada): {mensagem_inicial_sasl}")
        print(f"Mensagem SASL inicial (hex): {mensagem_inicial_sasl.hex()}") # DEBUG: Hex representation
        sock.sendall(mensagem_inicial_sasl)
        print("Mensagem SASL inicial (Client First Message) enviada.")

        # 2. Receber SASLContinue (Server First Message)
        tipo_mensagem = sock.recv(1)
        print(f"Tipo de mensagem recebido (SASL Continue expected): {chr(ord(tipo_mensagem))} (hex: {tipo_mensagem.hex()})") # DEBUG: Message type received
        if ord(tipo_mensagem) != ord('N'): # Espera SASLContinue
            if ord(tipo_mensagem) == ord('E'): # Tratar mensagem de erro
                tamanho_mensagem_bytes = sock.recv(4)
                tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
                corpo_mensagem_erro = sock.recv(tamanho_mensagem)
                mensagem_erro = corpo_mensagem_erro.decode('utf-8', errors='ignore') # Tentar decodificar a mensagem de erro
                print(f"Erro do servidor (SASL): {mensagem_erro}", file=sys.stderr) # Imprimir a mensagem de erro
                return False
            print(f"Esperava mensagem SASLContinue, recebeu: Tipo de mensagem (código numérico): {ord(tipo_mensagem)}, Tipo de mensagem (caractere): {chr(ord(tipo_mensagem))}", file=sys.stderr)
            return False
        tamanho_mensagem_bytes = sock.recv(4)
        tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
        corpo_mensagem = sock.recv(tamanho_mensagem)
        print(f"Corpo mensagem SASL Continue (hex): {corpo_mensagem.hex()}") # DEBUG: Hex of server message body
        server_first_message_b64 = corpo_mensagem.split(b'\x00')[0] # Pegar o primeiro bloco antes do null terminator
        server_first_message_str = base64.b64decode(server_first_message_b64).decode('utf-8')
        server_attrs = dict(attr.split('=', 1) for attr in server_first_message_str.split(','))
        print("Mensagem SASL Continue (Server First Message) recebida.")

        # Extrair salt, nonce do servidor e iteration count
        salt_b64 = server_attrs['s']
        server_nonce = server_attrs['r']
        iteration_count = int(server_attrs['i'])
        salt = base64.b64decode(salt_b64)

        # 3. Construir Client Final Message e enviar SASLResponse
        client_final_message_without_proof = construir_client_final_message_without_proof(client_nonce, server_nonce)
        client_proof = calcular_client_proof(usuario, senha, salt, iteration_count, client_first_message, server_first_message_str, client_final_message_without_proof)
        client_final_message = f"{client_final_message_without_proof},p={base64.b64encode(client_proof).decode('utf-8')}"
        mensagem_resposta_sasl = construir_mensagem_resposta_sasl(client_final_message)
        print(f"Mensagem SASL Response (codificada): {mensagem_resposta_sasl}")
        print(f"Mensagem SASL Response (hex): {mensagem_resposta_sasl.hex()}") # DEBUG: Hex representation
        sock.sendall(mensagem_resposta_sasl)
        print("Mensagem SASL Response (Client Final Message) enviada.")

        # 4. Receber SASLComplete (Server Final Message - opcional) ou Authentication OK
        tipo_mensagem = sock.recv(1)
        print(f"Tipo de mensagem recebido (SASL Complete or Auth OK expected): {chr(ord(tipo_mensagem))} (hex: {tipo_mensagem.hex()})") # DEBUG: Message type received
        if ord(tipo_mensagem) == ord('N'): # SASLComplete (Server Signature - Opcional, but good to verify)
            tamanho_mensagem_bytes = sock.recv(4)
            tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
            corpo_mensagem = sock.recv(tamanho_mensagem)
            print(f"Corpo mensagem SASL Complete (hex): {corpo_mensagem.hex()}") # DEBUG: Hex of server message body
            server_final_message_b64 = corpo_mensagem.split(b'\x00')[0]
            server_final_message_str = base64.b64decode(server_final_message_b64).decode('utf-8')
            server_signature_b64 = server_final_message_str.split('v=')[1]
            server_signature = base64.b64decode(server_signature_b64)
            print("Mensagem SASL Continue (Server Final Message) recebida e assinatura verificada (implementação de verificação omitida neste exemplo para simplificação).") # Implementação de verificação da assinatura do servidor seria ideal aqui.

            # Esperar Authentication OK após SASLComplete (ou diretamente se não houver SASLComplete)
            tipo_mensagem_auth_ok = sock.recv(1)
            print(f"Tipo de mensagem recebido (Auth OK expected after SASL Complete): {chr(ord(tipo_mensagem_auth_ok))} (hex: {tipo_mensagem_auth_ok.hex()})") # DEBUG: Message type received
            if ord(tipo_mensagem_auth_ok) == ord('R'):
                tipo_auth_ok = struct.unpack('!i', sock.recv(4))[0]
                if tipo_auth_ok == 0: # Authentication OK
                    print("Autenticação SCRAM-SHA-256 bem-sucedida!")
                    return True
                else:
                    print(f"Falha na autenticação após SASL Complete, tipo: {tipo_auth_ok}", file=sys.stderr)
                    return False
            else:
                print(f"Esperava Authentication OK após SASL Complete, recebeu: {chr(ord(tipo_mensagem_auth_ok))}", file=sys.stderr)
                return False

        elif ord(tipo_mensagem) == ord('R'): # Authentication OK directly
            tipo_auth_ok = struct.unpack('!i', sock.recv(4))[0]
            if tipo_auth_ok == 0: # Authentication OK
                print("Autenticação SCRAM-SHA-256 bem-sucedida!")
                return True
            else:
                print(f"Falha na autenticação SCRAM-SHA-256, tipo: {tipo_auth_ok}", file=sys.stderr)
                return False
        else:
            print(f"Esperava SASLComplete ou Authentication OK, recebeu: {chr(ord(tipo_mensagem))}", file=sys.stderr)
            return False


    except Exception as e:
        print(f"Erro durante autenticação SCRAM: {str(e)}", file=sys.stderr)
        return False
    
# ------------------- Funções auxiliares SCRAM-SHA-256 -------------------
def gerar_nonce(tamanho=24):
    """Gera um nonce (número aleatório) para SCRAM."""
    return base64.b64encode(os.urandom(tamanho)).decode('utf-8')

def construir_client_first_message(usuario, client_nonce):
    """Constrói a mensagem inicial do cliente (Client First Message)."""
    gs2_header = "n,,"  # Header GS2 correto para PostgreSQL (sem binding)
    username = f"n={preparar_nome_usuario(usuario)}"
    nonce = f"r={client_nonce}"

    # Aqui, montamos a mensagem corretamente, SEM repetir 'n,,'
    client_first_message_bare = f"{username},{nonce}"
    
    return gs2_header, client_first_message_bare  # Retornar separadamente

def construir_client_final_message_without_proof(client_nonce, server_nonce):
    """Constrói a mensagem final do cliente (Client Final Message) sem a prova."""
    channel_binding = 'c=biws'  # Sem channel binding
    nonce = f"r={server_nonce}"  # Certificar-se de usar o nonce completo

    return f"{channel_binding},{nonce}"

def construir_mensagem_inicial_sasl(client_first_message):
    """Constrói a mensagem SASLInitialResponse corretamente."""
    gs2_header, client_first_message_bare = client_first_message  # Separando GS2 header do restante
    
    mecanismo = b'SCRAM-SHA-256\x00'  # Nome do mecanismo SASL com null terminator
    payload = (gs2_header + client_first_message_bare).encode('utf-8')  # Unir corretamente

    mensagem_corpo = mecanismo + struct.pack('!I', len(payload)) + payload
    tamanho_mensagem = len(mensagem_corpo) + 4  # O tamanho da mensagem inclui os 4 bytes extras

    return b'p' + struct.pack('!I', tamanho_mensagem) + mensagem_corpo

def construir_mensagem_resposta_sasl(client_final_message):
    """Constrói a mensagem SASLResponse corretamente."""
    payload = client_final_message.encode('utf-8')  # Apenas encode para bytes

    tamanho_mensagem = len(payload) + 4  # O tamanho inclui os 4 bytes do próprio tamanho
    return b'p' + struct.pack('!I', tamanho_mensagem) + payload

def calcular_client_proof(usuario, senha, salt, iteration_count, client_first_message, server_first_message, client_final_message_without_proof):
    """Calcula a prova do cliente usando HMAC-SHA-256."""
    SaltedPassword = hi(senha, salt, iteration_count)
    ClientKey = hmac_sha256(SaltedPassword, 'Client Key')
    StoredKey = hash_sha256(ClientKey)
    auth_message = client_first_message + "," + server_first_message + "," + client_final_message_without_proof
    ClientSignature = hmac_sha256(StoredKey, auth_message)
    return ClientKey ^ ClientSignature # XOR bit a bit

def hi(senha, salt, iteration_count):
    """Implementa a função Hi (SaltedPasswordIteration)."""
    if iteration_count <= 0:
        raise ValueError("Iteration count deve ser positivo")
    U = pbkdf2_sha256(senha, salt, iteration_count, dkLen=32) # dkLen é o tamanho do hash SHA-256
    return U

def pbkdf2_sha256(senha, salt, iterations, dkLen):
    """Wrapper para PBKDF2-SHA-256."""
    return hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, iterations, dkLen)

def hmac_sha256(key, data):
    """Wrapper para HMAC-SHA-256."""
    return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

def hash_sha256(data):
    """Wrapper para SHA-256."""
    return hashlib.sha256(data).digest()

def xor_bytes(b1, b2):
    """Realiza XOR byte a byte em duas strings de bytes."""
    if len(b1) != len(b2):
        raise ValueError("Bytes devem ter o mesmo comprimento para XOR")
    return bytes(x ^ y for x, y in zip(b1, b2))


def preparar_nome_usuario(usuario):
    """Prepara o nome de usuário para SCRAM (escape de '=' e ',')."""
    return usuario.replace('=', '=3D').replace(',', '=2C')

def construir_mensagem_senha(senha_hash):
    """
    Constrói a mensagem de senha com o hash MD5.
    """
    senha_com_terminador = senha_hash.encode('utf-8') + b'\x00'
    tamanho = len(senha_com_terminador) + 4  # 4 bytes para o próprio tamanho
    return b'p' + struct.pack('!i', tamanho) + senha_com_terminador

def enviar_query(sock, query_string):
    """
    Envia uma query SQL para o servidor PostgreSQL.
    """
    mensagem_corpo = query_string.encode('utf-8') + b'\0'
    tamanho_mensagem = len(mensagem_corpo) + 4
    mensagem_completa = b'Q' + struct.pack('!i', tamanho_mensagem) + mensagem_corpo # 'Q' indica Query
    try:
        sock.sendall(mensagem_completa)
        print(f"Query enviada: {query_string}")
    except socket.error as e:
        print(f"Erro de socket ao enviar query: {e}", file=sys.stderr)
        return False # Indicar falha no envio
    except Exception as e:
        print(f"Erro inesperado ao enviar query: {e}", file=sys.stderr)
        return False
    return True # Indicar sucesso no envio

def receber_resultado(sock):
    """
    Recebe e imprime um resultado simplificado do servidor PostgreSQL.
    (Este é um tratamento de resultado muito básico e simplificado)
    """
    try:
        while True:
            tipo_mensagem = sock.recv(1)
            if not tipo_mensagem:
                print("Conexão fechada pelo servidor enquanto aguardava resultados.", file=sys.stderr)
                break # Conexão fechada

            tipo_mensagem_int = ord(tipo_mensagem)
            tamanho_mensagem_bytes = sock.recv(4)
            tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
            corpo_mensagem = sock.recv(tamanho_mensagem)

            if tipo_mensagem_int == ord('T'): # Row Description (Descrição das Colunas)
                print("Descrição das Colunas (Row Description) - Ignorando neste exemplo.")
                # Em uma implementação real, você processaria isso para saber os nomes e tipos das colunas
            elif tipo_mensagem_int == ord('D'): # Data Row (Linha de Dados)
                num_colunas = struct.unpack('!H', corpo_mensagem[:2])[0] # Número de colunas (2 bytes)
                offset = 2
                valores = []
                for _ in range(num_colunas):
                    tamanho_valor = struct.unpack('!i', corpo_mensagem[offset:offset+4])[0]
                    offset += 4
                    if tamanho_valor == -1: # Valor NULL
                        valores.append(None)
                    else:
                        valor = corpo_mensagem[offset:offset+tamanho_valor].decode('utf-8')
                        valores.append(valor)
                        offset += tamanho_valor
                print(f"Linha de Dados: {valores}")

            elif tipo_mensagem_int == ord('C'): # Command Complete (Comando Concluído)
                comando_completo = corpo_mensagem.decode('utf-8')
                print(f"Comando Completo: {comando_completo}")
                break # Após CommandComplete, para de receber resultados para esta query
            elif tipo_mensagem_int == ord('E'): # Error Message (Mensagem de Erro)
                erro_msg = corpo_mensagem.decode('utf-8', errors='ignore')
                print(f"Erro do Servidor ao receber resultado: {erro_msg}", file=sys.stderr)
                break # Para de receber resultados em caso de erro
            elif tipo_mensagem_int == ord('S'): # Parameter Status (Status de Parametro - ignoramos neste exemplo)
                pass # Ignoramos Parameter Status para este exemplo simples
            elif tipo_mensagem_int == ord('N'): # Notice Response (Avisos - ignoramos neste exemplo)
                pass # Ignoramos avisos para este exemplo simples
            else:
                print(f"Tipo de mensagem de resultado desconhecido: {chr(tipo_mensagem_int)} (código: {tipo_mensagem_int})", file=sys.stderr)
                break # Para de receber resultados em caso de tipo desconhecido
    except socket.error as e:
        print(f"Erro de socket ao receber resultado: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Erro inesperado ao receber resultado: {e}", file=sys.stderr)


if __name__ == "__main__":
    host = '127.0.0.1' # Ou o endereço IP do seu servidor PostgreSQL
    port = 5432      # Porta padrão do PostgreSQL
    usuario = 'postgres' # Substitua pelo seu usuário PostgreSQL
    senha = '123456'     # Substitua pela sua senha PostgreSQL
    banco_de_dados = 'postgres' # Substitua pelo seu banco de dados PostgreSQL

    conexao_socket = criar_conexao_postgres(host, port, usuario, banco_de_dados, senha)

    if conexao_socket:
        if enviar_query(conexao_socket, "SELECT 1;") : # Verificar se a query foi enviada com sucesso
            receber_resultado(conexao_socket)

        if enviar_query(conexao_socket, "SELECT version();"): # Verificar se a query foi enviada com sucesso
            receber_resultado(conexao_socket)

        if enviar_query(conexao_socket, "SELECT datname FROM pg_database;"): # Exemplo de query mais útil
            receber_resultado(conexao_socket)

        encerrar_conexao(conexao_socket) # Usar função para encerrar conexão explicitamente