from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from models.order import Order
from models.holding import Holding
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

router = APIRouter(prefix="/client", tags=["client"])

PENDING_STATES = {"NEW", "ACCEPTED", "PARTIALLY_FILLED"}

class HoldingOut(BaseModel):
    symbol: str
    quantity: int
    reserved_qty: int
    avg_price: float

class PendingOrderOut(BaseModel):
    id: int
    stock_symbol: str
    quantity: int
    filled_qty: int
    status: str
    order_type: str
    price: float

class PortfolioResponse(BaseModel):
    user_id: int
    cash_available: float
    cash_blocked: float
    holdings: List[HoldingOut]
    pending_orders: List[PendingOrderOut]
    generated_at: datetime

@router.get("/portfolio", response_model=PortfolioResponse)
def get_my_portfolio(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    user = current_user
    holdings = db.query(Holding).filter(Holding.user_id==user.id).all()
    orders = db.query(Order).filter(Order.user_id==user.id, Order.status.in_(PENDING_STATES)).all()
    return PortfolioResponse(
        user_id=user.id,
        cash_available=float(Decimal(str(user.cash_available or 0))),
        cash_blocked=float(Decimal(str(user.cash_blocked or 0))),
        holdings=[HoldingOut(symbol=h.symbol, quantity=h.quantity, reserved_qty=h.reserved_qty, avg_price=h.avg_price) for h in holdings],
        pending_orders=[PendingOrderOut(id=o.id, stock_symbol=o.stock_symbol, quantity=o.quantity, filled_qty=o.filled_qty, status=o.status or "", order_type=o.order_type, price=o.price or 0) for o in orders],
        generated_at=datetime.utcnow()
    )

class UnrealizedPnLItem(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    last_price: float
    unrealized_pnl: float

class UnrealizedPnLResponse(BaseModel):
    user_id: int
    total_unrealized_pnl: float
    items: List[UnrealizedPnLItem]
    pricing_source: str
    generated_at: datetime

def _stub_price(symbol: str) -> float:
    # TODO: replace with real market data service
    # naive deterministic placeholder (avoid external calls in tests)
    base = sum(ord(c) for c in symbol) % 100 + 50
    return float(base)

@router.get("/{user_id}/pnl/unrealized", response_model=UnrealizedPnLResponse)
def get_unrealized_pnl(user_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != user_id and current_user.role != 'trader':
        raise HTTPException(status_code=403, detail="Not authorized to view this user's PnL")
    holdings = db.query(Holding).filter(Holding.user_id==user_id).all()
    items: List[UnrealizedPnLItem] = []
    total = Decimal('0')
    for h in holdings:
        last_price = _stub_price(h.symbol)
        pnl = (Decimal(str(last_price)) - Decimal(str(h.avg_price))) * Decimal(h.quantity)
        items.append(UnrealizedPnLItem(symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price, last_price=last_price, unrealized_pnl=float(pnl)))
        total += pnl
    return UnrealizedPnLResponse(user_id=user_id, total_unrealized_pnl=float(total), items=items, pricing_source="stub", generated_at=datetime.utcnow())
