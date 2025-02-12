from Abstracts.Auth import Auth, Client

class SimpleTokenAuth(Auth):
    def __init__(self, expected_token: str):
        super().__init__(expected_token)

    def get_token(self, client: Client | None) -> str:
        return self.token

    def set_token(self, client: Client | None, token: str = "") -> str:
        self.token = token

    def validate_token(self, client: Client | None) -> bool:
        received_token = self.get_token(client)
        return received_token == self.token

    def generate_token(self) -> str:
        return self.generate_random_str(32)
