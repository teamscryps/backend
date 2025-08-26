from __future__ import annotations
import asyncio, random
import httpx
from .base import BrokerAdapter, BrokerSessionError, BrokerTemporaryError, BrokerPermanentError
from .types import PlaceOrderRequest, PlaceOrderResult, OrderStatus, SessionStatus

class ZerodhaAdapter(BrokerAdapter):
    BASE_URL = "https://api.kite.trade"

    def __init__(self, user):
        self.user = user

    def ensure_session(self, user) -> SessionStatus:
        # Placeholder: assume session valid if session_id present
        if not user.session_id:
            return SessionStatus(ok=False, refreshed=False, reason="no_session")
        return SessionStatus(ok=True)

    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult:
        payload = {
            "tradingsymbol": req.symbol,
            "exchange": "NSE",
            "transaction_type": req.side.upper(),
            "order_type": req.order_type,
            "quantity": req.quantity,
            "product": req.product,
        }
        if req.order_type == "LIMIT" and req.price is not None:
            payload["price"] = req.price
        attempt = 0
        last_exc = None
        while attempt < 3:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(f"{self.BASE_URL}/orders/regular", headers={"Authorization": f"token {self.user.session_id}"}, data=payload)
                if resp.status_code == 200:
                    data = resp.json() if resp.headers.get("content-type"," ").startswith("application/json") else {"status_code": resp.status_code}
                    broker_id = data.get("data", {}).get("order_id") if isinstance(data, dict) else None
                    return PlaceOrderResult(status=OrderStatus.ACCEPTED, broker_order_id=broker_id, placed_qty=req.quantity, filled_qty=0, avg_fill_price=None, raw=data)
                if 500 <= resp.status_code < 600:
                    raise BrokerTemporaryError(f"Zerodha temp status {resp.status_code}")
                if resp.status_code == 401:
                    raise BrokerSessionError("Session invalid")
                raise BrokerPermanentError(f"Order rejected status {resp.status_code}")
            except BrokerTemporaryError as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random()*0.3)
                attempt += 1
            except (httpx.RequestError) as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random()*0.3)
                attempt += 1
            except (BrokerSessionError, BrokerPermanentError):
                raise
        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown temp error")

    async def cancel_order(self, broker_order_id: str):  # stub
        return {"status": "NOT_IMPLEMENTED"}

    async def get_order_status(self, broker_order_id: str):  # stub
        return {"status": "NOT_IMPLEMENTED"}
