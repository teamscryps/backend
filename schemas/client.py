from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional

class ClientBase(BaseModel):
    name: str
    email: EmailStr
    pan: str
    phone: str
    status: str = 'active'  # 'active', 'pending', 'inactive'
    broker_api_key: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    pan: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    broker_api_key: Optional[str] = None

class ClientOut(BaseModel):
    id: int
    name: str
    email: str
    pan: str
    phone: str
    status: str
    portfolio_value: float
    join_date: datetime
    broker_api_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ClientDetailsOut(ClientOut):
    allocated_funds: float
    remaining_funds: float
    total_pnl: float
    todays_pnl: float
    active_trades_count: int
    total_trades_count: int

class ResetResponse(BaseModel):
    success: bool
