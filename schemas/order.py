
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class OrderBase(BaseModel):
    stock_symbol:str
    quantity: int
    order_type: Literal["buy", "sell"]

class OrderCreate(OrderBase):
    user_id: int

class OrderOut(OrderBase):
    id: int
    user_id: int
    price: float
    mtf_enabled: bool
    order_executed_at: datetime | None

    class Config:
        from_attributes = True 