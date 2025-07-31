"""
REST API exception handling.
"""

class ApiException(Exception):
    def __init__(self, status=None, reason=None):
        self.status = status
        self.reason = reason
        super().__init__(f"API Exception: {status} - {reason}") 