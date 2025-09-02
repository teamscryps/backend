from pydantic import BaseModel, ConfigDict

class StockOptionOut(BaseModel):
    symbol: str
    name: str
    price: float
    mtf_amount: float

    model_config = ConfigDict(from_attributes=True)

class StockDetailsOut(BaseModel):
    symbol: str
    name: str
    price: float
    mtf_amount: float
    # Add more fields as needed

    model_config = ConfigDict(from_attributes=True)
