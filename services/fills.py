from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.order import Order
from models.user import User
from models.holding import Holding
from models.order_fill import OrderFill
from models.audit_log import AuditLog
import hashlib, json
from services.brokers.types import OrderStatus
from datetime import datetime
from event_bus import publish

class FillAlreadyApplied(Exception):
    pass

def _log(db: Session, actor_user_id: int | None, target_user_id: int | None, action: str, description: str, details: dict):
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last.hash if last and getattr(last, 'hash', None) else None
    payload = {
        'actor_user_id': actor_user_id,
        'target_user_id': target_user_id,
        'action': action,
        'description': description,
        'details': details,
        'prev_hash': prev_hash,
        'ts': datetime.utcnow().isoformat()
    }
    serial = json.dumps(payload, sort_keys=True).encode()
    h = hashlib.sha256(serial).hexdigest()
    db.add(AuditLog(actor_user_id=actor_user_id, target_user_id=target_user_id, action=action, description=description, details=details, created_at=datetime.utcnow(), prev_hash=prev_hash, hash=h))

def apply_fill(db: Session, order_id: int, quantity: int, price: float, broker_fill_id: str | None = None):
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    price_dec = Decimal(str(price))
    with db.begin_nested():
        order: Order | None = db.get(Order, order_id)
        if not order:
            raise ValueError("Order not found")
        user: User | None = db.get(User, order.user_id)
        if not user:
            raise ValueError("User not found for order")
        if broker_fill_id:
            existing = db.query(OrderFill).filter(OrderFill.order_id==order_id, OrderFill.broker_fill_id==broker_fill_id).first()
            if existing:
                raise FillAlreadyApplied()
        remaining_qty = order.quantity - order.filled_qty
        apply_qty = min(quantity, remaining_qty)
        if apply_qty <= 0:
            return order
        fill = OrderFill(order_id=order.id, broker_fill_id=broker_fill_id, quantity=apply_qty, price=price_dec)
        db.add(fill)
        prev_value = (order.avg_fill_price or Decimal('0')) * order.filled_qty if order.filled_qty else Decimal('0')
        new_value = prev_value + price_dec * apply_qty
        order.filled_qty += apply_qty
        order.avg_fill_price = (new_value / order.filled_qty).quantize(Decimal('0.0001'))
        if order.order_type == 'buy':
            cost = price_dec * apply_qty
            # move from blocked to holding
            user.cash_blocked = Decimal(str(user.cash_blocked or 0)) - cost
            if user.cash_blocked < Decimal('0'):
                user.cash_blocked = Decimal('0')
            holding = db.query(Holding).filter(Holding.user_id==user.id, Holding.symbol==order.stock_symbol).with_for_update().first()
            if not holding:
                holding = Holding(user_id=user.id, symbol=order.stock_symbol, quantity=0, avg_price=0)
                db.add(holding)
            prev_h_qty = holding.quantity
            prev_h_val = Decimal(str(holding.avg_price)) * prev_h_qty if prev_h_qty else Decimal('0')
            new_h_qty = prev_h_qty + apply_qty
            new_h_val = prev_h_val + cost
            holding.quantity = new_h_qty
            holding.avg_price = float((new_h_val / new_h_qty) if new_h_qty else Decimal('0'))
            # Audit funds debit consumption of blocked funds
            _log(db, None, user.id, 'FUNDS_DEBIT', f'Consumed blocked funds {float(cost)} for buy fill order {order.id}', {
                'order_id': order.id, 'qty': apply_qty, 'amount': float(cost)
            })
        else:  # sell
            proceeds = price_dec * apply_qty
            holding = db.query(Holding).filter(Holding.user_id==user.id, Holding.symbol==order.stock_symbol).with_for_update().first()
            if not holding or holding.quantity < apply_qty:
                raise ValueError("Insufficient holding during fill")
            if holding.reserved_qty >= apply_qty:
                holding.reserved_qty -= apply_qty
            else:
                holding.reserved_qty = 0
            holding.quantity -= apply_qty
            user.cash_available = Decimal(str(user.cash_available or 0)) + proceeds
            # Audit funds credit from sell
            _log(db, None, user.id, 'FUNDS_CREDIT', f'Credited proceeds {float(proceeds)} for sell fill order {order.id}', {
                'order_id': order.id, 'qty': apply_qty, 'amount': float(proceeds)
            })
        filled_complete = order.filled_qty == order.quantity
        if order.order_type == 'buy' and filled_complete and user.cash_blocked and user.cash_blocked > Decimal('0'):
            leftover = Decimal(str(user.cash_blocked))
            user.cash_available = Decimal(str(user.cash_available or 0)) + leftover
            user.cash_blocked = Decimal('0')
            _log(db, None, user.id, 'FUNDS_CREDIT', f'Released leftover blocked {float(leftover)} after full fill order {order.id}', {
                'order_id': order.id, 'amount': float(leftover)
            })
        order.status = OrderStatus.FILLED.value if filled_complete else OrderStatus.PARTIALLY_FILLED.value
    details = {'order_id': order.id, 'qty': apply_qty, 'price': float(price_dec), 'filled_qty': order.filled_qty, 'status': order.status}
    _log(db, None, user.id, 'FILL_APPLIED', f'Fill {apply_qty}@{price} on order {order.id}', details)
    publish('order.fill', details | {
        'user_id': user.id,
        'symbol': order.stock_symbol,
        'cash_available': float(user.cash_available or 0),
        'cash_blocked': float(user.cash_blocked or 0)
    })
    return order

def apply_cancel(db: Session, order_id: int, status: str):
    if status not in (OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value):
        raise ValueError("Invalid cancel/reject status")
    with db.begin_nested():
        order: Order | None = db.get(Order, order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status in (OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value, OrderStatus.FILLED.value):
            return order
        user: User | None = db.get(User, order.user_id)
        if not user:
            raise ValueError("User not found")
        # release remaining blocked for buy or reserved for sell
        if order.order_type == 'buy':
            remaining_qty = order.quantity - order.filled_qty
            if remaining_qty > 0:
                # Release entire remaining blocked amount
                user.cash_available = Decimal(str(user.cash_available or 0)) + Decimal(str(user.cash_blocked or 0))
                user.cash_blocked = Decimal('0')
        else:  # sell
            remaining_qty = order.quantity - order.filled_qty
            if remaining_qty > 0:
                holding = db.query(Holding).filter(Holding.user_id==user.id, Holding.symbol==order.stock_symbol).with_for_update().first()
                if holding and holding.reserved_qty:
                    release = min(holding.reserved_qty, remaining_qty)
                    holding.reserved_qty -= release
        order.status = status
    details = {'order_id': order.id, 'status': status}
    _log(db, None, user.id, 'ORDER_' + status, f'Order {status.lower()}', details)
    publish('order.cancel', details | {
        'user_id': user.id,
        'cash_available': float(user.cash_available or 0),
        'cash_blocked': float(user.cash_blocked or 0)
    })
    return order