from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime


class TraderClientOut(BaseModel):
    id: int
    name: Optional[str] = None
    email: EmailStr
    capital: int
    cash_available: float | None = None
    cash_blocked: float | None = None
    broker: Optional[str] = None
    session_active: bool
    last_active: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TraderClientTradeOut(BaseModel):
    id: int
    user_id: int
    trader_id: Optional[int] = None
    stock_ticker: str
    buy_price: float | None = None
    sell_price: float | None = None
    quantity: int
    capital_used: float
    status: str
    type: str
    order_executed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TraderOrderResponse(BaseModel):
    order_id: int | None = None  # prefer order_id going forward
    trade_id: int | None = None  # backward compat for old clients (duplicate value)
    status: str
    message: str | None = None
