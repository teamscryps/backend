from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

class OrderStatus(str, Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

@dataclass
class PlaceOrderRequest:
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    order_type: str  # MARKET or LIMIT
    price: Optional[float]
    product: str  # CNC / MTF / DELIVERY / etc
    validity: str = "DAY"
    client_order_id: Optional[str] = None
    user_id: Optional[int] = None  # internal user id (client)

@dataclass
class PlaceOrderResult:
    status: OrderStatus
    broker_order_id: Optional[str]
    placed_qty: int
    filled_qty: int
    avg_fill_price: Optional[float]
    raw: Any

@dataclass
class SessionStatus:
    ok: bool
    refreshed: bool = False
    reason: Optional[str] = None
