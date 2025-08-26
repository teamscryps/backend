from __future__ import annotations
import asyncio, random
from .base import BrokerAdapter, BrokerTemporaryError, BrokerPermanentError, BrokerSessionError
from .types import PlaceOrderRequest, PlaceOrderResult, OrderStatus, SessionStatus

try:
    from growwapi import GrowwAPI  # type: ignore
except ImportError:
    GrowwAPI = None  # type: ignore

class GrowwAdapter(BrokerAdapter):
    def __init__(self, user):
        self.user = user

    def ensure_session(self, user) -> SessionStatus:
        if not user.session_id:
            return SessionStatus(ok=False, refreshed=False, reason="no_session")
        return SessionStatus(ok=True)

    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult:
        if GrowwAPI is None:
            raise BrokerPermanentError("Groww SDK not installed")
        attempt = 0
        last_exc = None
        while attempt < 3:
            try:
                groww = GrowwAPI(self.user.session_id)
                r = groww.place_order(
                    symbol=req.symbol,
                    exchange="NSE",
                    transaction_type=req.side.upper(),
                    order_type=req.order_type,
                    quantity=req.quantity,
                    product="MTF" if req.product == "MTF" else "DELIVERY"
                )
                success = bool(r.get("success"))
                if success:
                    return PlaceOrderResult(status=OrderStatus.ACCEPTED, broker_order_id=r.get("order_id"), placed_qty=req.quantity, filled_qty=0, avg_fill_price=None, raw=r)
                raise BrokerPermanentError("Groww order failed")
            except BrokerPermanentError:
                raise
            except Exception as e:  # network or temp
                last_exc = e
                await asyncio.sleep(0.3 + random.random()*0.3)
                attempt += 1
        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown error")

    async def cancel_order(self, broker_order_id: str):
        return {"status": "NOT_IMPLEMENTED"}

    async def get_order_status(self, broker_order_id: str):
        return {"status": "NOT_IMPLEMENTED"}
