import requests
from _typeshed import Incomplete

class BaseBeaconSession(requests.Session):
    base_url: Incomplete
    def __init__(self, base_url) -> None: ...
    def request(self, method, url, *args, **kwargs): ...
