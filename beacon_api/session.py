import requests
from packaging.version import Version

class BaseBeaconSession(requests.Session):
    def __init__(self, base_url: str):
        super().__init__()
        # e.g. "https://api.example.com/"
        self.base_url = base_url.rstrip("/") + "/"
        self.beacon_node_version = self.fetch_version()

    def fetch_version(self) -> Version:
        """Fetch the beacon node version from the server"""
        response = self.get("/api/info")
        if response.status_code != 200:
            raise Exception(f"Failed to get server info: {response.text}. Failed to connect to beacon node: {self.base_url}.")
        info = response.json()
        version_str = info['beacon_version']
        return Version(version_str)

    def request(self, method, url, *args, **kwargs):
        # if the URL is relative, prepend base_url
        if not url.startswith(("http://", "https://")):
            url = self.base_url + url.lstrip("/")
        return super().request(method, url, *args, **kwargs)
    
    def version_at_least(self, major: int, minor: int = 0, patch: int = 0) -> bool:
        """Check if the beacon node version is at least the specified version"""
        required_version = Version(f"{major}.{minor}.{patch}")
        return self.beacon_node_version >= required_version
    
    def is_admin(self) -> bool:
        """Check if the session has admin privileges"""
        response = self.get("/api/admin/check")
        if response.status_code == 401:
            return False
        if response.status_code != 200:
            raise Exception(f"Failed to check admin status: {response.text}")
        data = response.json()
        return data.get("is_admin", False)
