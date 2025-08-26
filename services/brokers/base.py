from __future__ import annotations
from typing import Protocol
from .types import PlaceOrderRequest, PlaceOrderResult, SessionStatus

class BrokerAdapter(Protocol):
    def ensure_session(self, user) -> SessionStatus: ...
    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult: ...
    async def cancel_order(self, broker_order_id: str): ...  # stub
    async def get_order_status(self, broker_order_id: str): ...  # stub

# Exceptions for unified error mapping
class BrokerError(Exception):
    code = "broker_error"

class BrokerSessionError(BrokerError):
    code = "session_error"

class BrokerRateLimitError(BrokerError):
    code = "rate_limit"

class BrokerTemporaryError(BrokerError):
    code = "temporary_error"

class BrokerPermanentError(BrokerError):
    code = "permanent_error"
