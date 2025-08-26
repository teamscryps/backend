from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from models.user import User
from models.holding import Holding
from models.order import Order
from models.order_fill import OrderFill
from models.portfolio_snapshot import PortfolioSnapshot
from models.audit_log import AuditLog
from services.brokers.types import OrderStatus
from sqlalchemy import func

# Placeholder market price fetcher; replace with real feed integration
def get_market_price(symbol: str) -> float:
    # Simple deterministic stub: hash-based pseudo price around 100-500
    h = sum(ord(c) for c in symbol)
    return 50 + (h % 300)

def compute_realized_pnl(db: Session, user_id: int) -> Decimal:
    """FIFO realized PnL using fills (OrderFill) across symbols.

    Strategy:
    - Gather all fills for user sorted by time.
    - Maintain FIFO queue of open buy lots per symbol (qty, price).
    - On sell fill, match against buy lots reducing qty and computing PnL.
    NOTE: Assumes all sells have prior buys (no shorting)."""
    fills = (
        db.query(OrderFill, Order)
        .join(Order, OrderFill.order_id == Order.id)
        .filter(Order.user_id == user_id, Order.filled_qty > 0)
        .order_by(OrderFill.created_at.asc(), OrderFill.id.asc())
        .all()
    )
    from collections import defaultdict, deque
    lots: dict[str, deque[tuple[int, Decimal]]] = defaultdict(deque)
    realized = Decimal('0')
    for fill, order in fills:
        qty = fill.quantity
        price = Decimal(str(fill.price))
        symbol = order.stock_symbol
        if order.order_type == 'buy':
            lots[symbol].append((qty, price))
        else:  # sell
            remaining = qty
            while remaining > 0 and lots[symbol]:
                lot_qty, lot_price = lots[symbol][0]
                take = min(lot_qty, remaining)
                realized += (price - lot_price) * take
                if take == lot_qty:
                    lots[symbol].popleft()
                else:
                    lots[symbol][0] = (lot_qty - take, lot_price)
                remaining -= take
            # If remaining >0 and no lots, treat as zero cost basis (shouldn't happen unless short)
            if remaining > 0:
                realized += price * remaining
    return realized

def snapshot_user(db: Session, user: User, snap_date: date) -> PortfolioSnapshot:
    holdings = db.query(Holding).filter(Holding.user_id==user.id).all()
    unrealized_total = Decimal('0')
    holding_rows = []
    for h in holdings:
        mkt = Decimal(str(get_market_price(h.symbol)))
        unreal = (mkt - Decimal(str(h.avg_price))) * Decimal(h.quantity)
        unrealized_total += unreal
        holding_rows.append({
            'symbol': h.symbol,
            'quantity': h.quantity,
            'avg_price': float(h.avg_price),
            'market_price': float(mkt),
            'unrealized': float(unreal)
        })
    realized = compute_realized_pnl(db, user.id)
    snap = PortfolioSnapshot(
        user_id=user.id,
        snapshot_date=snap_date,
        cash_available=user.cash_available or 0,
        cash_blocked=user.cash_blocked or 0,
        realized_pnl=realized,
        unrealized_pnl=unrealized_total,
        holdings=holding_rows
    )
    db.add(snap)
    return snap

def run_daily_snapshots(db: Session, snap_date: date | None = None) -> int:
    snap_date = snap_date or date.today()
    users = db.query(User).filter(User.role=='client').all()
    count = 0
    for u in users:
        snapshot_user(db, u, snap_date)
        count += 1
    db.commit()
    return count
