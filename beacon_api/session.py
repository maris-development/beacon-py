import requests

class BaseBeaconSession(requests.Session):
    def __init__(self, base_url):
        super().__init__()
        # e.g. "https://api.example.com/"
        self.base_url = base_url.rstrip("/") + "/"

    def request(self, method, url, *args, **kwargs):
        # if the URL is relative, prepend base_url
        if not url.startswith(("http://", "https://")):
            url = self.base_url + url.lstrip("/")
        return super().request(method, url, *args, **kwargs)
