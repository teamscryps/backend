
from pydantic import BaseModel
from datetime import datetime

class TradeBase(BaseModel):
    price: float
    quantity: int

class TradeCreate(TradeBase):
    order_id: int

class TradeOut(TradeBase):
    id: int
    order_id: int
    stock_ticker: str
    buy_price: float
    sell_price: float | None
    capital_used: float
    order_executed_at: datetime
    status: str
    brokerage_charge: float | None
    mtf_charge: float | None
    type: str

    class Config:
        orm_mode=True