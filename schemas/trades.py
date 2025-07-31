from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional

class TradeBase(BaseModel):
    price: float
    quantity: int

class TradeCreate(TradeBase):
    order_id: int
    stock_ticker: str
    type: str  # Changed to match model field
    order_type: str  # "buy" or "sell"
    buy_price: Optional[float] = None
    brokerage_charge: Optional[float] = None
    mtf_charge: Optional[float] = None

    @validator("type")
    def validate_type(cls, v):
        valid_types = ["eq", "mtf"]
        if v not in valid_types:
            raise ValueError("Trade type must be 'eq' or 'mtf'")
        return v

    @validator("order_type")
    def validate_order_type(cls, v):
        valid_types = ["buy", "sell"]
        if v not in valid_types:
            raise ValueError("Order type must be 'buy' or 'sell'")
        return v

class TradeOut(TradeBase):
    id: int
    user_id: int
    order_id: int
    stock_ticker: str
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    capital_used: float
    order_executed_at: datetime
    status: str
    brokerage_charge: Optional[float] = None
    mtf_charge: Optional[float] = None
    type: str  # Changed from trade_type to match model field

    @validator("status")
    def validate_status(cls, v):
        valid_statuses = ["open", "closed"]
        if v not in valid_statuses:
            raise ValueError("Status must be 'open' or 'closed'")
        return v

    @validator("type")
    def validate_type(cls, v):
        valid_types = ["eq", "mtf"]
        if v not in valid_types:
            raise ValueError("Trade type must be 'eq' or 'mtf'")
        return v

    class Config:
        from_attributes = True