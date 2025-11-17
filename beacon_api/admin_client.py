
from beacon_api.client import Client


class AdminClient(Client):
    def __init__(self, url: str, admin_username: str, admin_password: str, proxy_headers: dict[str, str] | None = None):
        super().__init__(url, proxy_headers=proxy_headers, basic_auth=(admin_username, admin_password))
        
        
    