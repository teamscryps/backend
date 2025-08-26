from __future__ import annotations
import asyncio, random
import upstox_client
from upstox_client.rest import ApiException
from .base import BrokerAdapter, BrokerTemporaryError, BrokerPermanentError, BrokerSessionError
from .types import PlaceOrderRequest, PlaceOrderResult, OrderStatus, SessionStatus
from config import settings

class UpstoxAdapter(BrokerAdapter):
    def __init__(self, user):
        self.user = user

    def ensure_session(self, user) -> SessionStatus:
        if not user.session_id:
            return SessionStatus(ok=False, refreshed=False, reason="no_session")
        return SessionStatus(ok=True)

    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult:
        attempt = 0
        last_exc = None
        while attempt < 3:
            try:
                config = upstox_client.Configuration()
                config.access_token = self.user.session_id
                config.api_key = settings.UPSTOX_API_KEY
                api = upstox_client.OrderApi(upstox_client.ApiClient(config))
                r = api.place_order(
                    quantity=req.quantity,
                    product="M" if req.product == "MTF" else "D",
                    validity=req.validity,
                    price=req.price or 0,
                    tag="",
                    instrument_token=req.symbol,
                    order_type=req.order_type,
                    transaction_type=req.side.upper(),
                    disclosed_quantity=0,
                    trigger_price=0,
                    is_amo=False
                )
                if hasattr(r, 'order_id'):
                    return PlaceOrderResult(status=OrderStatus.ACCEPTED, broker_order_id=r.order_id, placed_qty=req.quantity, filled_qty=0, avg_fill_price=None, raw=r.to_dict() if hasattr(r, 'to_dict') else r.__dict__)
                raise BrokerPermanentError("Upstox order failed")
            except ApiException as e:
                if e.status == 401:
                    raise BrokerSessionError("Session invalid")
                if 500 <= e.status < 600:
                    last_exc = e
                    await asyncio.sleep(0.3 + random.random()*0.3)
                    attempt += 1
                else:
                    raise BrokerPermanentError(f"Upstox error {e.status}")
            except Exception as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random()*0.3)
                attempt += 1
        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown error")

    async def cancel_order(self, broker_order_id: str):
        return {"status": "NOT_IMPLEMENTED"}

    async def get_order_status(self, broker_order_id: str):
        return {"status": "NOT_IMPLEMENTED"}
