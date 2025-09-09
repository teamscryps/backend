from __future__ import annotations
import asyncio, random
import httpx
from .base import BrokerAdapter, BrokerSessionError, BrokerTemporaryError, BrokerPermanentError
from .types import PlaceOrderRequest, PlaceOrderResult, OrderStatus, SessionStatus

class ICICIAdapter(BrokerAdapter):
    BASE_URL = "https://api.icicidirect.com"

    def __init__(self, user):
        self.user = user

    def ensure_session(self, user) -> SessionStatus:
        # Check if session is valid (access token present)
        if not user.session_id:
            return SessionStatus(ok=False, refreshed=False, reason="no_session")
        return SessionStatus(ok=True)

    async def place_order(self, req: PlaceOrderRequest) -> PlaceOrderResult:
        payload = {
            "symbol": req.symbol,
            "side": req.side.upper(),
            "quantity": req.quantity,
            "order_type": req.order_type,
            "product": req.product,
            "exchange": "NSE",
            "validity": req.validity
        }

        if req.order_type == "LIMIT" and req.price is not None:
            payload["price"] = req.price

        attempt = 0
        last_exc = None

        while attempt < 3:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    headers = {
                        "Authorization": f"Bearer {self.user.session_id}",
                        "Content-Type": "application/json"
                    }
                    resp = await client.post(f"{self.BASE_URL}/orders", headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    broker_id = data.get("order_id")
                    return PlaceOrderResult(
                        status=OrderStatus.ACCEPTED,
                        broker_order_id=broker_id,
                        placed_qty=req.quantity,
                        filled_qty=0,
                        avg_fill_price=None,
                        raw=data
                    )
                elif resp.status_code == 201:
                    data = resp.json()
                    broker_id = data.get("order_id")
                    return PlaceOrderResult(
                        status=OrderStatus.ACCEPTED,
                        broker_order_id=broker_id,
                        placed_qty=req.quantity,
                        filled_qty=0,
                        avg_fill_price=None,
                        raw=data
                    )
                elif 500 <= resp.status_code < 600:
                    raise BrokerTemporaryError(f"ICICI temp status {resp.status_code}")
                elif resp.status_code == 401:
                    raise BrokerSessionError("Session invalid")
                elif resp.status_code == 403:
                    raise BrokerSessionError("Access forbidden")
                else:
                    raise BrokerPermanentError(f"Order rejected status {resp.status_code}")

            except BrokerTemporaryError as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (BrokerSessionError, BrokerPermanentError):
                raise

        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown temp error")

    async def cancel_order(self, broker_order_id: str):
        """Cancel an order"""
        attempt = 0
        last_exc = None

        while attempt < 3:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    headers = {
                        "Authorization": f"Bearer {self.user.session_id}",
                        "Content-Type": "application/json"
                    }
                    resp = await client.delete(f"{self.BASE_URL}/orders/{broker_order_id}", headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    return {"status": "cancelled", "data": data}
                elif 500 <= resp.status_code < 600:
                    raise BrokerTemporaryError(f"ICICI temp status {resp.status_code}")
                elif resp.status_code == 401:
                    raise BrokerSessionError("Session invalid")
                else:
                    raise BrokerPermanentError(f"Cancel failed status {resp.status_code}")

            except BrokerTemporaryError as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (BrokerSessionError, BrokerPermanentError):
                raise

        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown temp error")

    async def get_order_status(self, broker_order_id: str):
        """Get order status"""
        attempt = 0
        last_exc = None

        while attempt < 3:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    headers = {
                        "Authorization": f"Bearer {self.user.session_id}",
                        "Content-Type": "application/json"
                    }
                    resp = await client.get(f"{self.BASE_URL}/orders/{broker_order_id}", headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    return {"status": "success", "data": data}
                elif 500 <= resp.status_code < 600:
                    raise BrokerTemporaryError(f"ICICI temp status {resp.status_code}")
                elif resp.status_code == 401:
                    raise BrokerSessionError("Session invalid")
                else:
                    raise BrokerPermanentError(f"Status check failed status {resp.status_code}")

            except BrokerTemporaryError as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e
                await asyncio.sleep(0.3 + random.random() * 0.3)
                attempt += 1
            except (BrokerSessionError, BrokerPermanentError):
                raise

        raise BrokerTemporaryError(str(last_exc) if last_exc else "Unknown temp error")
