from pydantic import BaseModel, ConfigDict

class WatchlistStockOut(BaseModel):
    id: int
    symbol: str
    name: str
    currentPrice: float
    previousClose: float
    change: float
    changePercent: float
    high: float
    low: float
    volume: str

    model_config = ConfigDict(from_attributes=True)

class WatchlistStockCreate(BaseModel):
    symbol: str

    model_config = ConfigDict(from_attributes=True)

class WatchlistSearchResult(BaseModel):
    symbol: str
    name: str
    currentPrice: float
    changePercent: float

    model_config = ConfigDict(from_attributes=True)
