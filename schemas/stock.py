from pydantic import BaseModel, ConfigDict
from typing import Optional

class StockOptionOut(BaseModel):
    symbol: str
    name: str
    price: Optional[float]
    mtf_amount: Optional[float]

    model_config = ConfigDict(from_attributes=True)

class StockDetailsOut(BaseModel):
    symbol: str
    name: str
    price: Optional[float]
    mtf_amount: Optional[float]
    # Add more fields as needed

    model_config = ConfigDict(from_attributes=True)
