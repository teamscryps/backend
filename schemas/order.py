
from pydantic import BaseModel, ConfigDict
from typing import Literal
from datetime import datetime

class OrderBase(BaseModel):
    stock_symbol:str
    quantity: int
    order_type: Literal["buy", "sell"]

class OrderCreate(OrderBase):
    user_id: int

class OrderOut(BaseModel):
    id: int
    client_id: int  # user_id
    stock: str  # stock_symbol
    name: str  # Will be fetched
    quantity: int
    price: float
    type: str  # order_type
    mtf_enabled: bool
    status: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)