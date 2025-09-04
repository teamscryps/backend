from pydantic import BaseModel, ConfigDict
from typing import Optional

class WatchlistStockOut(BaseModel):
    id: int
    symbol: str
    name: str
    currentPrice: Optional[float]
    previousClose: Optional[float]
    change: Optional[float]
    changePercent: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volume: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class WatchlistStockCreate(BaseModel):
    symbol: str

    model_config = ConfigDict(from_attributes=True)

class WatchlistSearchResult(BaseModel):
    symbol: str
    name: str
    currentPrice: Optional[float]
    changePercent: Optional[float]

    model_config = ConfigDict(from_attributes=True)
