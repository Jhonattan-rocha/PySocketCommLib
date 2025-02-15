import socket
import struct
import sys
import hashlib
import hmac
import base64
import os

class PostgreSQLSocketClient:
    def __init__(self, host, port, usuario, banco_de_dados, senha):
        """
        Inicializa o cliente PostgreSQL com as informações de conexão.
        """
        self.host = host
        self.port = port
        self.usuario = usuario
        self.banco_de_dados = banco_de_dados
        self.senha = senha
        self.conexao_socket = None # Inicializa a conexão_socket como None
        self.pid: int = 0
        self.secret_key: str = ""

    def conectar(self):
        """
        Cria e estabelece a conexão com o servidor PostgreSQL.
        Retorna True se a conexão for bem-sucedida, False caso contrário.
        """
        self.conexao_socket = self._criar_conexao_postgres(self.host, self.port, self.usuario, self.banco_de_dados, self.senha)
        return self.conexao_socket is not None

    def desconectar(self):
        """
        Encerra a conexão com o servidor PostgreSQL.
        """
        self._encerrar_conexao(self.conexao_socket)
        self.conexao_socket = None # Reseta a conexão_socket após desconectar

    def run(self, query_string):
        """
        Executa uma query SQL e retorna os resultados.
        Retorna uma lista de listas, onde cada lista interna representa uma linha de dados.
        Retorna None em caso de erro ao enviar ou receber dados.
        """
        if not self.conexao_socket:
            print("Erro: Conexão não estabelecida. Use conectar() primeiro.", file=sys.stderr)
            return None

        if self._enviar_query(self.conexao_socket, query_string): # Usando self._enviar_query
            return self._receber_resultado(self.conexao_socket) # Usando self._receber_resultado
        else:
            return None


    def _criar_conexao_postgres(self, host, port, usuario, banco_de_dados, senha):
        """
        Cria uma conexão PostgreSQL usando sockets diretamente.
        (Método interno da classe para criar a conexão)
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            print(f"Conectado a {host}:{port}")

            startup_message = self._construir_mensagem_startup(usuario, banco_de_dados) # Usando self._construir_mensagem_startup
            sock.sendall(startup_message)
            print("Mensagem de Startup enviada.")

            if not self._lidar_autenticacao(sock, usuario, senha): # Usando self._lidar_autenticacao
                print("Falha na autenticação.")
                self._encerrar_conexao(sock) # Usando self._encerrar_conexao
                return None
            print("Autenticação bem-sucedida.")

            return sock

        except socket.error as e:
            print(f"Erro de socket ao conectar a {host}:{port}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Erro inesperado ao criar conexão: {e}", file=sys.stderr)
            return None
        finally:
            if not sock:
                if sock:
                    self._encerrar_conexao(sock) # Usando self._encerrar_conexao

    def _encerrar_conexao(self, sock):
        """
        Encerra a conexão de socket de forma segura.
        (Método interno da classe para encerrar a conexão)
        """
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                print("Conexão encerrada.")
            except socket.error as e:
                print(f"Erro ao encerrar conexão: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Erro inesperado ao encerrar conexão: {e}", file=sys.stderr)


    def _construir_mensagem_startup(self, usuario, banco_de_dados):
        """
        Constrói a mensagem de Startup para o PostgreSQL.
        (Método interno da classe para construir a mensagem de startup)
        """
        parametros = {
            'user': usuario,
            'database': banco_de_dados
        }

        parametros_str = ""
        for chave, valor in parametros.items():
            parametros_str += chave + '\0' + valor + '\0'
        parametros_str += '\0'

        mensagem_corpo = struct.pack('!i', 196608) + parametros_str.encode('utf-8')
        tamanho_mensagem = len(mensagem_corpo) + 4
        mensagem_completa = struct.pack('!i', tamanho_mensagem) + mensagem_corpo
        return mensagem_completa

    def _lidar_autenticacao(self, sock, usuario, senha):
        """
        Lida com o processo de autenticação, incluindo MD5 e SCRAM-SHA-256.
        (Método interno da classe para lidar com a autenticação)
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
                        hash_md5 = self._calcular_md5(usuario, senha, salt) # Usando self._calcular_md5
                        mensagem_senha = self._construir_mensagem_senha(hash_md5) # Usando self._construir_mensagem_senha
                        sock.sendall(mensagem_senha)
                    elif tipo_autenticacao == 10:  # SASL Authentication
                        mecanismos_sasl = corpo_mensagem[4:].split(b'\x00')
                        if b'SCRAM-SHA-256' in mecanismos_sasl:
                            print("Servidor suporta SCRAM-SHA-256. Iniciando autenticação SCRAM.")
                            if not self._lidar_autenticacao_scram_sha_256(sock, usuario, senha): # Usando self._lidar_autenticacao_scram_sha_256
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

    def _calcular_md5(self, usuario, senha, salt):
        """
        Calcula o hash MD5 para autenticação.
        (Método interno da classe para calcular MD5)
        """
        temp_hash = hashlib.md5(senha.encode('utf-8') + usuario.encode('utf-8')).hexdigest().encode('utf-8')
        final_hash = hashlib.md5(temp_hash + salt).hexdigest()
        return f"md5{final_hash}"

    def _construir_mensagem_senha(self, senha_hash):
        """
        Constrói a mensagem de senha com o hash MD5.
        (Método interno da classe para construir mensagem de senha MD5)
        """
        senha_com_terminador = senha_hash.encode('utf-8') + b'\x00'
        tamanho = len(senha_com_terminador) + 4
        return b'p' + struct.pack('!i', tamanho) + senha_com_terminador

    def _lidar_autenticacao_scram_sha_256(self, sock, usuario, senha):
        """
        Lida com o processo de autenticação SCRAM-SHA-256.
        (Método interno da classe para lidar com SCRAM-SHA-256)
        """
        try:
            # 1. Enviar SASLInitialResponse (Client First Message)
            client_nonce = self._gerar_nonce() # Usando self._gerar_nonce
            client_first_message = self._construir_client_first_message(usuario, client_nonce) # Usando self._construir_client_first_message
            mensagem_inicial_sasl = self._construir_mensagem_inicial_sasl(client_first_message) # Usando self._construir_mensagem_inicial_sasl

            sock.sendall(mensagem_inicial_sasl)
            print("Mensagem SASL inicial (Client First Message) enviada.")

            while True:
                tipo_mensagem = sock.recv(1)
                if not tipo_mensagem:
                    print("Conexão fechada pelo servidor inesperadamente.", file=sys.stderr)
                    return False

                tamanho_mensagem_bytes = sock.recv(4)
                tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
                corpo_mensagem = sock.recv(tamanho_mensagem)

                if tipo_mensagem == b'R':  # Authentication Request
                    tipo_autenticacao = struct.unpack('!i', corpo_mensagem[:4])[0]

                    if tipo_autenticacao == 11:  # AuthenticationSASLContinue
                        server_first_message = corpo_mensagem[4:].decode('utf-8')
                        atributos_servidor = dict(attr.split('=', 1) for attr in server_first_message.split(','))

                        server_nonce = atributos_servidor['r']
                        salt_b64 = atributos_servidor['s']
                        iteration_count = int(atributos_servidor['i'])

                        salt = base64.b64decode(salt_b64)

                        # 2. Construir Client Final Message e enviar SASLResponse
                        client_final_message_without_proof = self._construir_client_final_message_without_proof(client_nonce, server_nonce) # Usando self._construir_client_final_message_without_proof
                        client_proof = self._calcular_client_proof(usuario, senha, salt, iteration_count, client_first_message, server_first_message, client_final_message_without_proof) # Usando self._calcular_client_proof

                        client_final_message = f"{client_final_message_without_proof},p={base64.b64encode(client_proof).decode('utf-8')}"
                        mensagem_resposta_sasl = self._construir_mensagem_resposta_sasl(client_final_message) # Usando self._construir_mensagem_resposta_sasl
                        sock.sendall(mensagem_resposta_sasl)
                        print("Mensagem SASL Response (Client Final Message) enviada.")

                    elif tipo_autenticacao == 12:  # AuthenticationSASLFinal
                        server_final_message = corpo_mensagem[4:].decode('utf-8')
                        print(f"Server Final Message: {server_final_message}")

                        if "v=" in server_final_message:
                            print("Autenticação SCRAM-SHA-256 bem-sucedida!")
                            return True
                        else:
                            print("Falha na verificação da assinatura do servidor.", file=sys.stderr)
                            return False

                    elif tipo_autenticacao == 0:  # Authentication OK
                        print("Autenticação SCRAM-SHA-256 bem-sucedida!")
                        return True

                    else:
                        print(f"Método de autenticação inesperado: {tipo_autenticacao}", file=sys.stderr)
                        return False

                elif tipo_mensagem == b'E':  # Mensagem de erro do servidor
                    erro_msg = corpo_mensagem.decode('utf-8', errors='ignore')
                    print(f"Erro do Servidor: {erro_msg}", file=sys.stderr)
                    return False

                else:
                    print(f"Tipo de mensagem inesperado: {tipo_mensagem}", file=sys.stderr)
                    return False

        except Exception as e:
            print(f"Erro durante autenticação SCRAM: {str(e)}", file=sys.stderr)
            return False


    def _gerar_nonce(self, tamanho=24):
        """Gera um nonce (número aleatório) para SCRAM."""
        return base64.b64encode(os.urandom(tamanho)).decode('utf-8')

    def _construir_client_first_message(self, usuario, client_nonce):
        """Constrói a mensagem inicial do cliente (Client First Message)."""
        gs2_header = "n,,"
        username = f"n={self._preparar_nome_usuario(usuario)}" # Usando self._preparar_nome_usuario
        nonce = f"r={client_nonce}"

        client_first_message_bare = f"{username},{nonce}"

        return gs2_header, client_first_message_bare

    def _construir_client_final_message_without_proof(self, client_nonce, server_nonce):
        """Constrói a mensagem final do cliente (Client Final Message) sem a prova."""
        channel_binding = 'c=biws'
        nonce = f"r={server_nonce}"

        return f"{channel_binding},{nonce}"

    def _construir_mensagem_inicial_sasl(self, client_first_message):
        """Constrói a mensagem SASLInitialResponse corretamente."""
        gs2_header, client_first_message_bare = client_first_message

        mecanismo = b'SCRAM-SHA-256\x00'
        payload = (gs2_header + client_first_message_bare).encode('utf-8')

        mensagem_corpo = mecanismo + struct.pack('!I', len(payload)) + payload
        tamanho_mensagem = len(mensagem_corpo) + 4

        return b'p' + struct.pack('!I', tamanho_mensagem) + mensagem_corpo

    def _construir_mensagem_resposta_sasl(self, client_final_message):
        """Constrói a mensagem SASLResponse corretamente."""
        payload = client_final_message.encode('utf-8')

        tamanho_mensagem = len(payload) + 4
        return b'p' + struct.pack('!I', tamanho_mensagem) + payload

    def _calcular_client_proof(self, usuario, senha, salt, iteration_count, client_first_message, server_first_message, client_final_message_without_proof):
        """Calcula a prova do cliente usando HMAC-SHA-256."""
        SaltedPassword = self._hi(senha, salt, iteration_count) # Usando self._hi
        ClientKey = self._hmac_sha256(SaltedPassword, 'Client Key') # Usando self._hmac_sha256
        StoredKey = self._hash_sha256(ClientKey) # Usando self._hash_sha256

        _, client_first_message_bare = client_first_message

        auth_message = client_first_message_bare + "," + server_first_message + "," + client_final_message_without_proof

        ClientSignature = self._hmac_sha256(StoredKey, auth_message) # Usando self._hmac_sha256

        return self._xor_bytes(ClientKey, ClientSignature) # Usando self._xor_bytes

    def _hi(self, senha, salt, iteration_count):
        """Implementa a função Hi (SaltedPasswordIteration)."""
        if iteration_count <= 0:
            raise ValueError("Iteration count deve ser positivo")
        U = self._pbkdf2_sha256(senha, salt, iteration_count, dkLen=32) # Usando self._pbkdf2_sha256
        return U

    def _pbkdf2_sha256(self, senha, salt, iterations, dkLen):
        """Wrapper para PBKDF2-SHA-256."""
        return hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, iterations, dkLen)

    def _hmac_sha256(self, key, data):
        """Wrapper para HMAC-SHA-256."""
        return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

    def _hash_sha256(self, data):
        """Wrapper para SHA-256."""
        return hashlib.sha256(data).digest()

    def _xor_bytes(self, b1, b2):
        """Realiza XOR byte a byte em duas strings de bytes."""
        if len(b1) != len(b2):
            raise ValueError("Bytes devem ter o mesmo comprimento para XOR")
        return bytes(x ^ y for x, y in zip(b1, b2))


    def _preparar_nome_usuario(self, usuario):
        """Prepara o nome de usuário para SCRAM (escape de '=' e ',')."""
        return usuario.replace('=', '=3D').replace(',', '=2C')

    def _enviar_query(self, sock, query_string):
        """
        Envia uma query SQL para o servidor PostgreSQL.
        (Método interno da classe para enviar queries)
        """
        mensagem_corpo = query_string.encode('utf-8') + b'\0'
        tamanho_mensagem = len(mensagem_corpo) + 4
        mensagem_completa = b'Q' + struct.pack('!i', tamanho_mensagem) + mensagem_corpo
        try:
            sock.sendall(mensagem_completa)
            print(f"Query enviada: {query_string}")
            return True
        except socket.error as e:
            print(f"Erro de socket ao enviar query: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Erro inesperado ao enviar query: {e}", file=sys.stderr)
            return False

    def _receber_resultado(self, sock):
        """
        Recebe e processa o resultado do servidor PostgreSQL.
        Retorna uma lista de listas contendo as linhas de dados.
        Retorna None em caso de erro ou se não houver dados.
        """
        resultados = []
        colunas = [] # Lista para armazenar nomes das colunas
        try:
            while True:
                tipo_mensagem = sock.recv(1)
                if not tipo_mensagem:
                    print("Conexão fechada pelo servidor enquanto aguardava resultados.", file=sys.stderr)
                    break

                tipo_mensagem_int = ord(tipo_mensagem)
                tamanho_mensagem_bytes = sock.recv(4)
                tamanho_mensagem = struct.unpack('!i', tamanho_mensagem_bytes)[0] - 4
                corpo_mensagem = sock.recv(tamanho_mensagem)

                if tipo_mensagem_int == ord('T'): # Row Description
                    num_campos = struct.unpack('!H', corpo_mensagem[:2])[0]
                    offset = 2
                    nomes_colunas = []
                    for _ in range(num_campos):
                        nome_fim = corpo_mensagem.find(b'\x00', offset)
                        nome_coluna = corpo_mensagem[offset:nome_fim].decode('utf-8')
                        nomes_colunas.append(nome_coluna)
                        offset = nome_fim + 1
                        # Ignoramos o resto das informações do campo por agora (tipo de dado, etc.)
                    colunas = nomes_colunas # Armazena os nomes das colunas
                    print(f"Nomes das colunas recebidos: {colunas}") # Imprime os nomes das colunas recebidos
                elif tipo_mensagem_int == ord('D'): # Data Row
                    num_colunas = struct.unpack('!H', corpo_mensagem[:2])[0]
                    offset = 2
                    valores_linha = []
                    for _ in range(num_colunas):
                        tamanho_valor = struct.unpack('!i', corpo_mensagem[offset:offset+4])[0]
                        offset += 4
                        if tamanho_valor == -1:
                            valores_linha.append(None)
                        else:
                            valor = corpo_mensagem[offset:offset+tamanho_valor].decode('utf-8')
                            valores_linha.append(valor)
                            offset += tamanho_valor
                    resultados.append(valores_linha) # Adiciona a linha de dados aos resultados
                elif tipo_mensagem_int == ord('C'): # Command Complete
                    comando_completo = corpo_mensagem.decode('utf-8')
                    print(f"Comando Completo: {comando_completo}")
                    break # Fim dos resultados para esta query
                elif tipo_mensagem_int == ord('E'): # Error Message
                    erro_msg = corpo_mensagem.decode('utf-8', errors='ignore')
                    print(f"Erro do Servidor ao receber resultado: {erro_msg}", file=sys.stderr)
                    return None # Retorna None em caso de erro
                elif tipo_mensagem_int == ord('S'): # Parameter Status
                    pass # Ignoramos Parameter Status
                elif tipo_mensagem_int == ord('N'): # Notice Response
                    pass # Ignoramos avisos
                elif tipo_mensagem_int == ord('K'):
                    self.pid = struct.unpack('!i', corpo_mensagem[:4])[0]
                    self.secret_key = struct.unpack('!i', corpo_mensagem[4:8])[0]
                elif tipo_mensagem_int == ord('Z'): # ReadyForQuery
                    transaction_status = chr(corpo_mensagem[0]) # Estado da transação é o primeiro byte
                    print(f"Mensagem ReadyForQuery recebida - Estado da Transação: {transaction_status}")
                else:
                    print(f"Tipo de mensagem de resultado desconhecido: {chr(tipo_mensagem_int)} (código: {tipo_mensagem_int})", file=sys.stderr)
                    break # Para em caso de tipo desconhecido
            if colunas and resultados: # Se houver nomes de colunas e resultados, imprima de forma organizada
                print("\nResultados:")
                print("-" * 40)
                print("| " + " | ".join(colunas) + " |")
                print("-" * 40)
                for linha in resultados:
                    print("| " + " | ".join(linha) + " |")
                print("-" * 40)
            elif resultados: # Se não houver nomes de colunas mas houver resultados, imprima apenas os dados
                print("\nResultados (sem nomes de colunas):")
                for linha in resultados:
                    print(linha)
            return resultados # Retorna os resultados processados
        except socket.error as e:
            print(f"Erro de socket ao receber resultado: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Erro inesperado ao receber resultado: {e}", file=sys.stderr)
            return None
        
if __name__ == "__main__":
    db = PostgreSQLSocketClient(host='127.0.0.1', port=5432, usuario='postgres', senha='123456', banco_de_dados='postgres')
    if db.conectar():
        print(db.run("SELECT version();"))
        print(db.run("SELECT version();"))
        print(db.run("SELECT datname FROM pg_database;"))
        db.desconectar()
