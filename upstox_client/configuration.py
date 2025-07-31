"""
Configuration for Upstox API client.
"""

class Configuration:
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.access_token = None
        self.api_key = None
    
    def retrieve_access_token(self, auth_code: str) -> str:
        """Placeholder method to retrieve access token."""
        return f"upstox_token_{auth_code}" 