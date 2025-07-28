from pydantic import BaseModel
from typing import Literal

class OrderBase(BaseModel):
    stock_symbol:str
    quantity: int
    order_type: Literal["buy", "sell"]

class OrderCreate(OrderBase):
    user_id: int

class OrderOut(OrderBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True 
