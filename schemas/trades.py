from pydantic import BaseModel

class TradeBase(BaseModel):
    price: float
    quantity: int

class TradeCreate(TradeBase):
    order_id: int

class TradeOut(TradeBase):
    id: int
    order_id: int

    class Config:
        orm_mode=True