from Abstracts.Auth import Auth, Client

class NoAuth(Auth):
    def __init__(self):
        super().__init__(None) 

    def get_token(self, client: Client) -> str:
        return ""

    def set_token(self, client: Client) -> str:
        return ""

    def validate_token(self, client: Client) -> bool:
        return True

    def generate_token(self) -> str:
        return ""