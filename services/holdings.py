"""Holdings domain service: encapsulates create/update logic and validations.

Functions:
- apply_buy(db, user_id, symbol, quantity, price) -> Holding (rejects explicit non-positive price)
- validate_sell(db, user_id, symbol, quantity) -> Holding (raises if invalid)
- apply_sell(db, user_id, symbol, quantity) -> Optional[Holding]
- get_holdings(db, user_id) -> List[Holding]
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from models.holding import Holding
from models.audit_log import AuditLog

class InsufficientHoldingsError(Exception):
    def __init__(self, symbol: str, have: int, want: int):
        super().__init__(f"Insufficient holdings for {symbol}: have {have}, want {want}")
        self.symbol = symbol
        self.have = have
        self.want = want


class InsufficientFundsError(Exception):
    def __init__(self, needed: float, available: float):
        super().__init__(f"Insufficient funds: need {needed}, have {available}")
        self.needed = needed
        self.available = available


def _get(db: Session, user_id: int, symbol: str) -> Optional[Holding]:
    return db.query(Holding).filter(Holding.user_id == user_id, Holding.symbol == symbol).first()


def apply_buy(db: Session, user_id: int, symbol: str, quantity: int, price: float | None) -> Holding:
    """Apply a buy to holdings.

    Rules:
    - quantity must be > 0 (implicit by caller; not revalidated here).
    - If price is provided explicitly (not None) it must be > 0. Zero/negative explicit prices are rejected.
      (Rationale: a zero-priced trade is almost certainly a data error; allowing it distorts average cost.)
    - If price is None we treat the cost contribution as zero but do NOT overwrite an existing avg_price unless
      there is some positive priced history (legacy behavior for placeholder trades).
    """
    if price is not None and price <= 0:
        raise ValueError("Price must be positive when provided")
    # Ensure pending objects visible when autoflush=False
    db.flush()
    holding = _get(db, user_id, symbol)
    if holding:
        total_cost_before = holding.avg_price * holding.quantity
        total_cost_new = (price or 0) * quantity
        new_qty = holding.quantity + quantity
        if new_qty > 0 and (total_cost_before + total_cost_new) > 0:
            holding.avg_price = (total_cost_before + total_cost_new) / new_qty
        holding.quantity = new_qty
        holding.last_updated = datetime.utcnow()
    else:
        holding = Holding(user_id=user_id, symbol=symbol, quantity=quantity, avg_price=(price or 0), last_updated=datetime.utcnow())
        db.add(holding)
    return holding


def validate_sell(db: Session, user_id: int, symbol: str, quantity: int) -> Holding:
    db.flush()
    holding = _get(db, user_id, symbol)
    if not holding or holding.quantity < quantity:
        raise InsufficientHoldingsError(symbol, holding.quantity if holding else 0, quantity)
    return holding


def apply_sell(db: Session, user_id: int, symbol: str, quantity: int) -> Optional[Holding]:
    # validate_sell already flushes
    holding = validate_sell(db, user_id, symbol, quantity)
    holding.quantity -= quantity
    if holding.quantity <= 0:
        db.delete(holding)
        return None
    holding.last_updated = datetime.utcnow()
    return holding


def get_holdings(db: Session, user_id: int) -> List[Holding]:
    return db.query(Holding).filter(Holding.user_id == user_id).all()


def apply_buy_with_funds(db: Session, user, symbol: str, quantity: int, price: float):
    """Atomically deduct from cash_available for immediate execution style buy.

    (Reservation + blocked funds is handled elsewhere for real order flow.)
    """
    if price <= 0:
        raise ValueError("Price must be positive")
    cost = quantity * price
    available = float(user.cash_available or 0)
    if available < cost:
        raise InsufficientFundsError(cost, available)
    user.cash_available = available - cost
    holding = apply_buy(db, user.id, symbol, quantity, price)
    db.add(AuditLog(
        actor_user_id=user.id,
        target_user_id=user.id,
        action="FUNDS_DEBIT",
        description=f"Buy {symbol} x{quantity} @ {price}",
        details={"symbol": symbol, "qty": quantity, "price": price, "debit": cost, "remaining_cash": float(user.cash_available)},
        created_at=datetime.utcnow()
    ))
    return holding


def apply_sell_with_funds(db: Session, user, symbol: str, quantity: int, price: float):
    """Atomically apply sell and credit cash_available (immediate settlement assumption)."""
    if price <= 0:
        raise ValueError("Price must be positive")
    holding = apply_sell(db, user.id, symbol, quantity)
    proceeds = quantity * price
    user.cash_available = float(user.cash_available or 0) + proceeds
    db.add(AuditLog(
        actor_user_id=user.id,
        target_user_id=user.id,
        action="FUNDS_CREDIT",
        description=f"Sell {symbol} x{quantity} @ {price}",
        details={"symbol": symbol, "qty": quantity, "price": price, "credit": proceeds, "new_cash": float(user.cash_available)},
        created_at=datetime.utcnow()
    ))
    return holding
