import socket
import ssl
import struct
import sys
import hashlib
import hmac
import base64
import os
import logging

class PostgreSQLSocketClient:
    def __init__(self, host, port, username, database_name, password, use_ssl=False, ssl_certfile=None, ssl_keyfile=None):
        """
        Inicializa o cliente PostgreSQL com as informações de conexão.
        """
        self.host = host
        self.port = port
        self.username = username
        self.database_name = database_name
        self.password = password
        self.socket_connection = None # Inicializa a socket_connection como None
        self.pid: int = 0
        self.secret_key: str = ""
        self.parameter_status = {}
        self.notices = []
        self.prepared_statements = {}
        logging.basicConfig(filename='./psql.txt', level=logging.INFO, encoding='cp850',
                            format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        self.use_ssl = use_ssl
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile

    def connect(self, time_out: int = 30):
        """
        Cria e estabelece a conexão com o servidor PostgreSQL.
        Retorna True se a conexão for bem-sucedida, False caso contrário.
        """
        self.socket_connection = self._create_postgres_connection(self.host, self.port, self.username, self.database_name, self.password)
        self.socket_connection.settimeout(time_out)
        return self.socket_connection is not None

    def disconnect(self):
        """
        Encerra a conexão com o servidor PostgreSQL.
        """
        self._close_connection(self.socket_connection)
        self.socket_connection = None # Reseta a socket_connection após desconectar

    def reconnect(self):
        """Tenta reconectar ao servidor PostgreSQL."""
        self.logger.info("Tentando reconexão...")
        self.disconnect()
        return self.connect()

    def run(self, query_string):
        """
        Executa uma query SQL e retorna os resultados.
        Retorna uma lista de listas, onde cada lista interna representa uma linha de dados.
        Retorna None em caso de erro ao enviar ou receber dados.
        """
        if not self.socket_connection:
            self.logger.error("Erro: Conexão não estabelecida. Use conectar() primeiro.")
            return None

        if self._send_query(self.socket_connection, query_string): # Usando self._send_query
            return self._receive_result(self.socket_connection) # Usando self._receive_result
        else:
            return None

    def _create_postgres_connection(self, host, port, username, database_name, password) -> socket.socket | ssl.SSLSocket:
        """
        Cria uma conexão PostgreSQL usando sockets diretamente.
        (Método interno da classe para criar a conexão)
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self.logger.info(f"Conectado a {host}:{port}")
            
            if self.use_ssl:
                self.logger.info("Estabelecendo conexão segura via SSL/TLS...")
                context = ssl.create_default_context()
                if self.ssl_certfile and self.ssl_keyfile:
                    context.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
                
                sock = context.wrap_socket(sock, server_hostname=self.host)
                self.logger.info("Conexão SSL estabelecida com sucesso.")

            startup_message = self._build_startup_message(username, database_name) # Usando self._build_startup_message
            sock.sendall(startup_message)
            self.logger.info("Mensagem de Startup enviada.")

            if not self._handle_authentication(sock, username, password): # Usando self._handle_authentication
                self.logger.error("Falha na autenticação.")
                self._close_connection(sock) # Usando self._close_connection
                return None
            self.logger.info("Autenticação bem-sucedida.")

            return sock

        except socket.error as e:
            self.logger.error(f"Erro de socket ao conectar a {host}:{port}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Erro inesperado ao criar conexão: {e}")
            return None
        finally:
            if not sock:
                if sock:
                    self._close_connection(sock) # Usando self._close_connection

    def _close_connection(self, sock):
        """
        Encerra a conexão de socket de forma segura.
        (Método interno da classe para encerrar a conexão)
        """
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                self.logger.info("Conexão encerrada.")
            except socket.error as e:
                self.logger.error(f"Erro ao encerrar conexão: {e}")
            except Exception as e:
                self.logger.error(f"Erro inesperado ao encerrar conexão: {e}")


    def _build_startup_message(self, username, database_name):
        """
        Constrói a mensagem de Startup para o PostgreSQL.
        (Método interno da classe para construir a mensagem de startup)
        """
        parameters = {
            'user': username,
            'database': database_name
        }

        parameters_str = ""
        for key, value in parameters.items():
            parameters_str += key + '\0' + value + '\0'
        parameters_str += '\0'

        message_body = struct.pack('!i', 196608) + parameters_str.encode('utf-8')
        message_size = len(message_body) + 4
        full_message = struct.pack('!i', message_size) + message_body
        return full_message

    def _handle_authentication(self, sock, username, password):
        """
        Lida com o processo de autenticação, incluindo MD5 e SCRAM-SHA-256.
        (Método interno da classe para lidar com a autenticação)
        """
        try:
            while True:
                message_type = sock.recv(1)
                if not message_type:
                    self.logger.error("Conexão fechada pelo servidor inesperadamente.")
                    return False

                message_type_int = ord(message_type)

                message_size_bytes = sock.recv(4)
                if len(message_size_bytes) < 4:
                    self.logger.error("Conexão fechada durante leitura do tamanho.")
                    return False

                message_size = struct.unpack('!i', message_size_bytes)[0] - 4
                message_body = b''
                while len(message_body) < message_size:
                    part = sock.recv(message_size - len(message_body))
                    if not part:
                        break
                    message_body += part

                if message_type_int == ord('E'):  # Error message
                    error_msg = message_body.decode('utf-8', errors='ignore')
                    self.logger.error(f"Erro do Servidor: {error_msg}")
                    return False
                elif message_type_int == ord('R'):  # Authentication Request
                    auth_type = struct.unpack('!i', message_body[:4])[0]
                    if auth_type == 5:  # MD5 Password
                        salt = message_body[4:8]
                        self.logger.info(f"Servidor solicitou autenticação MD5 (salt: {salt.hex()})")
                        md5_hash = self._calculate_md5_hash(username, password, salt) # Usando self._calculate_md5_hash
                        password_message = self._build_password_message(md5_hash) # Usando self._build_password_message
                        sock.sendall(password_message)
                    elif auth_type == 10:  # SASL Authentication
                        sasl_mechanisms = message_body[4:].split(b'\x00')
                        if b'SCRAM-SHA-256' in sasl_mechanisms:
                            self.logger.info("Servidor suporta SCRAM-SHA-256. Iniciando autenticação SCRAM.")
                            if not self._handle_scram_sha_256_authentication(sock, username, password): # Usando self._handle_scram_sha_256_authentication
                                return False
                        else:
                            self.logger.error(f"SCRAM-SHA-256 não suportado pelo servidor. Mecanismos suportados: {sasl_mechanisms}")
                            return False
                    elif auth_type == 0:  # Authentication OK
                        self.logger.info("Autenticação bem-sucedida!")
                        return True
                    else:
                        self.logger.error(f"Método de autenticação não suportado: {auth_type}")
                        return False
                elif message_type_int == ord('S'):  # ParameterStatus
                    message_body_str = message_body.decode('utf-8')
                    parts = message_body_str.split('\x00')
                    parameter_name = parts[0]
                    parameter_value = parts[1] if len(parts) > 1 and parts[1] else None # Verifica se há valor
                    self.parameter_status[parameter_name] = parameter_value # Armazena no dicionário
                else:
                    self.logger.error(f"Tipo de mensagem desconhecido: {message_type_int}")
                    return False
        except Exception as e:
            self.logger.error(f"Erro durante autenticação: {str(e)}")
            return False

    def _calculate_md5_hash(self, username, password, salt):
        """
        Calcula o hash MD5 para autenticação.
        (Método interno da classe para calcular MD5)
        """
        temp_hash = hashlib.md5(password.encode('utf-8') + username.encode('utf-8')).hexdigest().encode('utf-8')
        final_hash = hashlib.md5(temp_hash + salt).hexdigest()
        return f"md5{final_hash}"

    def _build_password_message(self, password_hash):
        """
        Constrói a mensagem de senha com o hash MD5.
        (Método interno da classe para construir mensagem de senha MD5)
        """
        password_with_terminator = password_hash.encode('utf-8') + b'\x00'
        size = len(password_with_terminator) + 4
        return b'p' + struct.pack('!i', size) + password_with_terminator

    def _handle_scram_sha_256_authentication(self, sock, username, password):
        """
        Lida com o processo de autenticação SCRAM-SHA-256.
        (Método interno da classe para lidar com SCRAM-SHA-256)
        """
        try:
            # 1. Enviar SASLInitialResponse (Client First Message)
            client_nonce = self._generate_nonce() # Usando self._generate_nonce
            client_first_message = self._build_client_first_message(username, client_nonce) # Usando self._build_client_first_message
            initial_sasl_message = self._build_initial_sasl_message(client_first_message) # Usando self._build_initial_sasl_message

            sock.sendall(initial_sasl_message)
            self.logger.info("Mensagem SASL inicial (Client First Message) enviada.")

            while True:
                message_type = sock.recv(1)
                if not message_type:
                    self.logger.error("Conexão fechada pelo servidor inesperadamente.")
                    return False

                message_size_bytes = sock.recv(4)
                message_size = struct.unpack('!i', message_size_bytes)[0] - 4
                message_body = sock.recv(message_size)

                if message_type == b'R':  # Authentication Request
                    auth_type = struct.unpack('!i', message_body[:4])[0]

                    if auth_type == 11:  # AuthenticationSASLContinue
                        server_first_message = message_body[4:].decode('utf-8')
                        server_attributes = dict(attr.split('=', 1) for attr in server_first_message.split(','))

                        server_nonce = server_attributes['r']
                        salt_b64 = server_attributes['s']
                        iteration_count = int(server_attributes['i'])

                        salt = base64.b64decode(salt_b64)

                        # 2. Construir Client Final Message e enviar SASLResponse
                        client_final_message_without_proof = self._build_client_final_message_without_proof(client_nonce, server_nonce) # Usando self._build_client_final_message_without_proof
                        client_proof = self._calculate_client_proof(username, password, salt, iteration_count, client_first_message, server_first_message, client_final_message_without_proof) # Usando self._calculate_client_proof

                        client_final_message = f"{client_final_message_without_proof},p={base64.b64encode(client_proof).decode('utf-8')}"
                        sasl_response_message = self._build_sasl_response_message(client_final_message) # Usando self._build_sasl_response_message
                        sock.sendall(sasl_response_message)
                        self.logger.info("Mensagem SASL Response (Client Final Message) enviada.")

                    elif auth_type == 12:  # AuthenticationSASLFinal
                        server_final_message = message_body[4:].decode('utf-8')
                        self.logger.info(f"Server Final Message: {server_final_message}")

                        if "v=" in server_final_message:
                            self.logger.info("Autenticação SCRAM-SHA-256 bem-sucedida!")
                            return True
                        else:
                            self.logger.error("Falha na verificação da assinatura do servidor.")
                            return False

                    elif auth_type == 0:  # Authentication OK
                        self.logger.info("Autenticação SCRAM-SHA-256 bem-sucedida!")
                        return True

                    else:
                        self.logger.error(f"Método de autenticação inesperado: {auth_type}")
                        return False

                elif message_type == b'E':  # Mensagem de erro do servidor
                    error_msg = message_body.decode('utf-8', errors='ignore')
                    self.logger.error(f"Erro do Servidor: {error_msg}")
                    return False

                else:
                    self.logger.error(f"Tipo de mensagem inesperado: {message_type}")
                    return False

        except Exception as e:
            self.logger.error(f"Erro durante autenticação SCRAM: {str(e)}")
            return False


    def _generate_nonce(self, size=24):
        """Gera um nonce (número aleatório) para SCRAM."""
        return base64.b64encode(os.urandom(size)).decode('utf-8')

    def _build_client_first_message(self, username, client_nonce):
        """Constrói a mensagem inicial do cliente (Client First Message)."""
        gs2_header = "n,,"
        user_identifier = f"n={self._prepare_username(username)}" # Usando self._prepare_username
        nonce = f"r={client_nonce}"

        client_first_message_bare = f"{user_identifier},{nonce}"

        return gs2_header, client_first_message_bare

    def _build_client_final_message_without_proof(self, client_nonce, server_nonce):
        """Constrói a mensagem final do cliente (Client Final Message) sem a prova."""
        channel_binding = 'c=biws'
        nonce = f"r={server_nonce}"

        return f"{channel_binding},{nonce}"

    def _build_initial_sasl_message(self, client_first_message):
        """Constrói a mensagem SASLInitialResponse corretamente."""
        gs2_header, client_first_message_bare = client_first_message

        mechanism = b'SCRAM-SHA-256\x00'
        payload = (gs2_header + client_first_message_bare).encode('utf-8')

        message_body = mechanism + struct.pack('!I', len(payload)) + payload
        message_size = len(message_body) + 4

        return b'p' + struct.pack('!I', message_size) + message_body

    def _build_sasl_response_message(self, client_final_message):
        """Constrói a mensagem SASLResponseMessage corretamente."""
        payload = client_final_message.encode('utf-8')

        message_size = len(payload) + 4
        return b'p' + struct.pack('!I', message_size) + payload

    def _calculate_client_proof(self, username, password, salt, iteration_count, client_first_message, server_first_message, client_final_message_without_proof):
        """Calcula a prova do cliente usando HMAC-SHA-256."""
        salted_password = self._hi(password, salt, iteration_count) # Usando self._hi
        client_key = self._hmac_sha256(salted_password, 'Client Key') # Usando self._hmac_sha256
        stored_key = self._hash_sha256(client_key) # Usando self._hash_sha256

        _, client_first_message_bare = client_first_message

        auth_message = client_first_message_bare + "," + server_first_message + "," + client_final_message_without_proof

        client_signature = self._hmac_sha256(stored_key, auth_message) # Usando self._hmac_sha256

        return self._xor_bytes(client_key, client_signature) # Usando self._xor_bytes

    def _hi(self, password, salt, iteration_count):
        """Implementa a função Hi (SaltedPasswordIteration)."""
        if iteration_count <= 0:
            raise ValueError("Iteration count deve ser positivo")
        U = self._pbkdf2_sha256(password, salt, iteration_count, dkLen=32) # Usando self._pbkdf2_sha256
        return U

    def _pbkdf2_sha256(self, password, salt, iterations, dkLen):
        """Wrapper para PBKDF2-SHA-256."""
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dkLen)

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


    def _prepare_username(self, username):
        """Prepara o nome de usuário para SCRAM (escape de '=' e ',')."""
        return username.replace('=', '=3D').replace(',', '=2C')

    def begin(self):
        """Inicia uma nova transação."""
        if not self.socket_connection:
            self.logger.error("Conexão não estabelecida.")
            return False
        return self.__send_command("BEGIN") 

    def commit(self):
        """Confirma a transação atual."""
        if not self.socket_connection:
            self.logger.error("Conexão não estabelecida.")
            return False
        return self.__send_command("COMMIT")

    def rollback(self):
        """Desfaz a transação atual."""
        if not self.socket_connection:
            self.logger.error("Conexão não estabelecida.")
            return False
        return self.__send_command("ROLLBACK")

    def __send_command(self, command_string):
        """Envia um comando SQL (BEGIN, COMMIT, ROLLBACK) para o servidor."""
        message_body = command_string.encode('utf-8') + b'\x00'
        message_size = len(message_body) + 4
        full_message = b'Q' + struct.pack('!i', message_size) + message_body
        try:
            self.socket_connection.sendall(full_message)
            self.logger.info(f"Comando enviado: {command_string}")
            return True
        except socket.error as e:
            self.logger.error(f"Erro de socket ao enviar comando: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Erro inesperado ao enviar comando: {e}")
            return False
    
    def _send_query(self, sock, query_string):
        """
        Envia uma query SQL para o servidor PostgreSQL.
        (Método interno da classe para enviar queries)
        """
        message_body = query_string.encode('utf-8') + b'\0'
        message_size = len(message_body) + 4
        full_message = b'Q' + struct.pack('!i', message_size) + message_body
        try:
            sock.sendall(full_message)
            self.logger.info(f"Query enviada: {query_string}")
            return True
        except socket.error as e:
            self.logger.error(f"Erro de socket ao enviar query: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Erro inesperado ao enviar query: {e}")
            return False

    def _get_data_type_info(self, data_type_oid):
        """
        Consulta pg_type para obter informações detalhadas sobre um tipo de dado.
        """
        query = f"""
            SELECT *
            FROM pg_type
            WHERE oid = {data_type_oid};
        """
        results = self.run(query)
        if results and results[0]:
            return results
        return None # Retorna None se não encontrar o tipo

    def _receive_result(self, sock):
        """
        Recebe e processa o resultado do servidor PostgreSQL.
        Retorna uma lista de listas contendo as linhas de dados.
        Retorna None em caso de erro ou se não houver dados.
        """
        results = []
        columns = [] # Lista para armazenar nomes das colunas
        try:
            while True:
                message_type = sock.recv(1)
                if not message_type:
                    self.logger.error("Conexão fechada pelo servidor enquanto aguardava resultados.")
                    break

                message_type_int = ord(message_type)
                message_size_bytes = sock.recv(4)
                message_size = struct.unpack('!i', message_size_bytes)[0] - 4
                message_body = sock.recv(message_size)

                if message_type_int == ord('T'): # Row Description
                    num_fields = struct.unpack('!H', message_body[:2])[0]
                    offset = 2
                    columns_info = [] # Lista para armazenar informações detalhadas sobre as colunas
                    for _ in range(num_fields):
                        name_end = message_body.find(b'\x00', offset)
                        column_name = message_body[offset:name_end].decode('utf-8')
                        offset = name_end + 1

                        table_oid = struct.unpack('!i', message_body[offset:offset+4])[0]
                        offset += 4
                        attribute_number = struct.unpack('!h', message_body[offset:offset+2])[0]
                        offset += 2
                        data_type_oid = struct.unpack('!i', message_body[offset:offset+4])[0]
                        offset += 4
                        data_type_size = struct.unpack('!h', message_body[offset:offset+2])[0]
                        offset += 2
                        type_modifier = struct.unpack('!i', message_body[offset:offset+4])[0]
                        offset += 4
                        format_code = struct.unpack('!h', message_body[offset:offset+2])[0]
                        offset += 2

                        columns_info.append({
                            'name': column_name,
                            'table_oid': table_oid,
                            'attribute_number': attribute_number,
                            'data_type_oid': data_type_oid,
                            'data_type_size': data_type_size,
                            'type_modifier': type_modifier,
                            'format_code': format_code
                        })
                    columns = columns_info
                    self.logger.info(f"Nomes das colunas recebidos: {columns}")
                elif message_type_int == ord('D'): # Data Row
                    num_columns = struct.unpack('!H', message_body[:2])[0]
                    offset = 2
                    row_values = []
                    for _ in range(num_columns):
                        value_size = struct.unpack('!i', message_body[offset:offset+4])[0]
                        offset += 4
                        if value_size == -1:
                            row_values.append(None)
                        else:
                            value = message_body[offset:offset+value_size].decode('utf-8')
                            row_values.append(value)
                            offset += value_size
                    results.append(row_values) # Adiciona a linha de dados aos resultados
                elif message_type_int == ord('C'): # Command Complete
                    command_complete = message_body.decode('utf-8')
                    self.logger.info(f"Comando Completo: {command_complete}")
                    break # Fim dos resultados para esta query
                elif message_type_int == ord('E'): # Error Message
                    error_msg = message_body.decode('utf-8', errors='ignore')
                    self.logger.error(f"Erro do Servidor ao receber resultado: {error_msg}")
                    return None # Retorna None em caso de erro
                elif message_type_int == ord('S'): # Parameter Status
                    message_body_str = message_body.decode('utf-8')
                    parts = message_body_str.split('\x00')
                    parameter_name = parts[0]
                    parameter_value = parts[1] if len(parts) > 1 and parts[1] else None # Verifica se há valor
                    self.parameter_status[parameter_name] = parameter_value # Armazena no dicionário
                elif message_type_int == ord('N'): # Notice Response
                    offset = 0
                    notice_details = {}
                    while offset < len(message_body):
                        field_type = chr(message_body[offset])
                        offset += 1
                        value_end = message_body.find(b'\x00', offset)
                        field_value = message_body[offset:value_end].decode('utf-8', errors='ignore')
                        notice_details[field_type] = field_value
                        if offset == len(message_body) or value_end == -1:
                            break
                        offset = value_end + 1
                    self.notices.append(notice_details) # Adiciona a notice à lista
                elif message_type_int == ord('K'):
                    self.pid = struct.unpack('!i', message_body[:4])[0]
                    self.secret_key = struct.unpack('!i', message_body[4:8])[0]
                elif message_type_int == ord('Z'): # ReadyForQuery
                    transaction_status = chr(message_body[0]) # Estado da transação é o primeiro byte
                    self.logger.info(f"Mensagem ReadyForQuery recebida - Estado da Transação: {transaction_status}")
                else:
                    self.logger.error(f"Tipo de mensagem de resultado desconhecido: {chr(message_type_int)} (código: {message_type_int})")
                    break # Para em caso de tipo desconhecido
            return results, columns # Retorna os resultados processados
        except socket.error as e:
            self.logger.error(f"Erro de socket ao receber resultado: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Erro inesperado ao receber resultado: {e}")
            return None
    
    def prepare_statement(self, statement_name, query_string, param_types=None):
        """Prepara um statement SQL no servidor."""
        if param_types is None:
            param_types = []
        
        # Construindo a mensagem `Prepare`
        message_body = statement_name.encode('utf-8') + b'\x00'  # Nome do statement
        message_body += query_string.encode('utf-8') + b'\x00'  # Query
        message_body += struct.pack('!H', len(param_types))  # Número de parâmetros

        # Adicionar os tipos dos parâmetros se existirem
        for param_type in param_types:
            message_body += struct.pack('!I', param_type)

        message_size = len(message_body) + 4
        full_message = b'P' + struct.pack('!I', message_size) + message_body

        # Criando mensagem `Sync`
        sync_message = b'S' + struct.pack('!I', 4)

        try:
            self.socket_connection.sendall(full_message)
            self.socket_connection.sendall(sync_message)
            self.logger.info(f"Statement preparado: {statement_name}")
            self.prepared_statements[statement_name] = query_string
            return True
        except Exception as e:
            self.logger.error(f"Erro ao preparar statement: {e}")
            return False

    def execute_prepared_statement(self, statement_name, parameters):
        """Executa um statement preparado com segurança contra SQL Injection."""
        if statement_name not in self.prepared_statements:
            self.logger.error(f"Statement '{statement_name}' não foi preparado.")
            return None

        num_params = len(parameters)

        # Criando a mensagem `Bind`
        bind_message = b'\x00' + statement_name.encode('utf-8') + b'\x00'  # Nome do portal (vazio) e do statement

        # Número de parâmetros no formato esperado pelo PostgreSQL
        bind_message += struct.pack('!H', num_params)

        # Especificando que todos os parâmetros são strings (formato de texto)
        for _ in range(num_params):
            bind_message += struct.pack('!H', 0)  # 0 significa formato de texto

        # Adicionando os valores dos parâmetros
        bind_message += struct.pack('!H', num_params)
        for param in parameters:
            param_bytes = param.encode('utf-8')
            bind_message += struct.pack('!I', len(param_bytes)) + param_bytes  # Inclui o tamanho e o valor

        # Formato do resultado (0 para texto)
        bind_message += struct.pack('!H', 0)

        # Criando a mensagem `Bind`
        full_bind_message = b'B' + struct.pack('!I', len(bind_message) + 4) + bind_message

        # Criando a mensagem `Execute` (Executar o portal vazio, retornando todas as linhas)
        execute_message = b'E' + struct.pack('!I', 9) + b'\x00' + struct.pack('!I', 0)

        # Criando `Sync` (Indica que terminamos a solicitação)
        sync_message = b'S' + struct.pack('!I', 4)

        try:
            # Enviar as mensagens corretamente
            self.socket_connection.sendall(full_bind_message)
            self.socket_connection.sendall(execute_message)
            self.socket_connection.sendall(sync_message)
            self.logger.info(f"Executando statement preparado: {statement_name}")

            # Receber e processar os resultados
            return self._receive_prepared_statement_result()
        except Exception as e:
            self.logger.error(f"Erro ao executar statement preparado: {e}")
            return None

    def _receive_prepared_statement_result(self):
            """
            Recebe e processa o resultado do servidor para statements preparados.
            Retorna uma lista de listas contendo as linhas de dados.
            Retorna None em caso de erro ou se não houver dados.
            """
            results = []
            columns = []
            try:
                while True:
                    message_type = self.socket_connection.recv(1)
                    if not message_type:
                        self.logger.error("Conexão fechada pelo servidor enquanto aguardava resultados.")
                        break

                    message_type_int = ord(message_type)
                    message_size_bytes = self.socket_connection.recv(4)
                    message_size = struct.unpack('!i', message_size_bytes)[0] - 4
                    message_body = self.socket_connection.recv(message_size)

                    if message_type_int == ord('1'):  # ParseComplete
                        self.logger.info("ParseComplete recebido.")
                        continue
                    elif message_type_int == ord('2'):  # BindComplete
                        self.logger.info("BindComplete recebido.")
                        continue
                    elif message_type_int == ord('T'):  # RowDescription
                        num_fields = struct.unpack('!H', message_body[:2])[0]
                        offset = 2
                        for _ in range(num_fields):
                            name_end = message_body.find(b'\x00', offset)
                            column_name = message_body[offset:name_end].decode('utf-8')
                            offset = name_end + 1 + 18  # Pular os metadados do campo
                            columns.append(column_name)
                        self.logger.info(f"Nomes das colunas recebidos: {columns}")
                    elif message_type_int == ord('D'):  # DataRow
                        num_columns = struct.unpack('!H', message_body[:2])[0]
                        offset = 2
                        row_values = []
                        for _ in range(num_columns):
                            value_size = struct.unpack('!i', message_body[offset:offset+4])[0]
                            offset += 4
                            if value_size == -1:
                                row_values.append(None)
                            else:
                                value = message_body[offset:offset+value_size].decode('utf-8')
                                row_values.append(value)
                                offset += value_size
                        results.append(row_values)  # Adiciona a linha de dados aos resultados
                    elif message_type_int == ord('C'):  # Command Complete
                        command_complete = message_body.decode('utf-8')
                        self.logger.info(f"Comando Completo: {command_complete}")
                        break  # Fim dos resultados para esta query
                    elif message_type_int == ord('S'): # Parameter Status
                        message_body_str = message_body.decode('utf-8')
                        parts = message_body_str.split('\x00')
                        parameter_name = parts[0]
                        parameter_value = parts[1] if len(parts) > 1 and parts[1] else None # Verifica se há valor
                        self.parameter_status[parameter_name] = parameter_value # Armazena no dicionário
                    elif message_type_int == ord('E'):  # Error Message
                        error_msg = message_body.decode('utf-8', errors='ignore')
                        self.logger.error(f"Erro do Servidor ao receber resultado: {error_msg}")
                        return None  # Retorna None em caso de erro
                    elif message_type_int == ord('Z'):  # ReadyForQuery
                        transaction_status = chr(message_body[0])  # Estado da transação é o primeiro byte
                        self.logger.info(f"Mensagem ReadyForQuery recebida - Estado da Transação: {transaction_status}")
                    elif message_type_int == ord('K'):
                        self.pid = struct.unpack('!i', message_body[:4])[0]
                        self.secret_key = struct.unpack('!i', message_body[4:8])[0]
                    else:
                        self.logger.error(f"Tipo de mensagem de resultado desconhecido: {chr(message_type_int)} (código: {message_type_int})")
                        break  # Para em caso de tipo desconhecido
                return results, columns  # Retorna os resultados processados
            except socket.error as e:
                self.logger.error(f"Erro de socket ao receber resultado: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Erro inesperado ao receber resultado: {e}")
                return None

if __name__ == "__main__":
    db = PostgreSQLSocketClient(host="localhost", port=5432, username="postgres", password="123456", database_name="postgres")
    if db.connect():
        result = db.run("CREATE TABLE IF NOT EXISTS minha_tabela (id SERIAL PRIMARY KEY, nome TEXT)")
        print(db.notices)
        print("Criado com sucesso")
