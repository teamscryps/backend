from pydantic import BaseModel, field_validator, ConfigDict
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

    @field_validator("type")
    def validate_type(cls, v):
        valid_types = ["eq", "mtf"]
        if v not in valid_types:
            raise ValueError("Trade type must be 'eq' or 'mtf'")
        return v

    @field_validator("order_type")
    def validate_order_type(cls, v):
        valid_types = ["buy", "sell"]
        if v not in valid_types:
            raise ValueError("Order type must be 'buy' or 'sell'")
        return v

class TradeOut(TradeBase):
    id: int
    user_id: int
    trader_id: Optional[int] = None
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

    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["open", "closed"]
        if v not in valid_statuses:
            raise ValueError("Status must be 'open' or 'closed'")
        return v

    @field_validator("type")
    def validate_type_out(cls, v):
        valid_types = ["eq", "mtf"]
        if v not in valid_types:
            raise ValueError("Trade type must be 'eq' or 'mtf'")
        return v

    model_config = ConfigDict(from_attributes=True)

class ActiveTradeOut(BaseModel):
    id: int
    stock: str  # stock_ticker
    name: str  # Will be fetched or set
    quantity: int
    buy_price: float
    current_price: float  # Need to fetch current price
    mtf_enabled: bool
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class TransactionOut(BaseModel):
    id: int
    stock: str
    name: str
    quantity: int
    buy_price: float
    current_price: float
    mtf_enabled: bool
    timestamp: datetime
    type: str  # 'buy' or 'sell'
    pnl: float
    pnl_percent: float

    model_config = ConfigDict(from_attributes=True)