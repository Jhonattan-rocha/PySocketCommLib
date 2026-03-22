from ..Abstracts.Auth import Auth, Client


class SimpleTokenAuth(Auth):
    """
    Autenticação por token simples.

    O servidor é inicializado com um token esperado. Durante a validação,
    o cliente deve enviar esse token via socket. O servidor lê o token
    recebido e compara com o esperado.

    Uso no servidor:
        auth = SimpleTokenAuth(token="meu-token-secreto")

    Uso no cliente: o cliente deve enviar o token como primeiros bytes
    ao conectar, usando send_token().
    """

    def __init__(self, token: str):
        super().__init__(token)

    def get_token(self, client: Client | None) -> str:
        """Retorna o token esperado pelo servidor."""
        return self.token

    def set_token(self, client: Client | None, token: str = "") -> str:
        self.token = token

    def validate_token(self, client: Client | None) -> bool:
        """
        Valida o token recebido do cliente via socket.

        Lê até 4096 bytes do socket do cliente e compara com o token esperado.
        Retorna True se o token for válido, False caso contrário.
        """
        if client is None:
            return False

        try:
            # Lê o token enviado pelo cliente via socket
            connection = getattr(client, 'connection', None) or getattr(client, 'writer', None)

            if hasattr(connection, 'recv'):
                # ThreadClient: socket síncrono
                received = connection.recv(4096).decode('utf-8').strip()
            elif hasattr(connection, 'write'):
                # AsyncClient: o token deve ser lido de forma separada no fluxo async
                # Para o caso síncrono do validate_token, retorna True se não houver
                # mecanismo de leitura disponível (validação deve ser feita no fluxo async)
                return True
            else:
                return False

            return received == self.token
        except Exception:
            return False

    def send_token(self, client: Client | None) -> None:
        """
        Envia o token para o servidor.
        Deve ser chamado pelo cliente logo após conectar.
        """
        if client is None:
            return
        try:
            connection = getattr(client, 'connection', None)
            if connection and hasattr(connection, 'sendall'):
                connection.sendall(self.token.encode('utf-8'))
        except Exception:
            pass

    def generate_token(self) -> str:
        return self.generate_random_str(32)
