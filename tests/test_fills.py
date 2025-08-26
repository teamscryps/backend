import asyncio
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models.user import User
from models.order import Order
from models.holding import Holding
from models.audit_log import AuditLog
from services.fills import apply_fill, apply_cancel
from services.brokers.types import OrderStatus

# Simple in-memory DB setup
engine = create_engine('sqlite://', connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

def new_user(session, funds=100000):
    u = User(name='U', email=f'u{funds}@e.com', password='x', mobile='1', api_key='k', api_secret='s', broker='zerodha', role='client', cash_available=Decimal(str(funds)), cash_blocked=0)
    session.add(u); session.commit(); session.refresh(u); return u

def test_buy_partial_and_full_fill_audits():
    db = SessionLocal()
    user = new_user(db, funds=10000)
    # Create buy order reserving funds manually similar to placement
    order = Order(user_id=user.id, stock_symbol='ABC', quantity=100, price=50, order_type='buy', status=OrderStatus.ACCEPTED.value, filled_qty=0, avg_fill_price=None)
    db.add(order)
    # Reserve 100*50=5000
    user.cash_available -= Decimal('5000')
    user.cash_blocked += Decimal('5000')
    db.commit(); db.refresh(order); db.refresh(user)
    # Partial fill 40 @50
    apply_fill(db, order.id, 40, 50)
    db.commit(); db.refresh(order); db.refresh(user)
    assert order.status == OrderStatus.PARTIALLY_FILLED.value
    assert order.filled_qty == 40
    assert user.cash_blocked == Decimal('3000')
    h = db.query(Holding).filter_by(user_id=user.id, symbol='ABC').first()
    assert h and h.quantity == 40
    # Full fill remaining 60
    apply_fill(db, order.id, 60, 50)
    db.commit(); db.refresh(order); db.refresh(user)
    assert order.status == OrderStatus.FILLED.value
    assert user.cash_blocked == 0
    assert user.cash_available == Decimal('10000') - Decimal('5000')  # spent funds, leftover released was zero since fully used
    # Audit logs
    acts = { (a.action, a.description) for a in db.query(AuditLog).all() }
    assert any(a[0]=='FUNDS_DEBIT' and 'buy fill' in a[1] for a in acts)
    assert any(a[0]=='FILL_APPLIED' for a in acts)


def test_sell_fill_and_cancel_release():
    db = SessionLocal()
    user = new_user(db, funds=5000)
    # Seed holding 50 ABC @ 10
    h = Holding(user_id=user.id, symbol='ABC', quantity=50, avg_price=10, reserved_qty=20)
    db.add(h)
    order = Order(user_id=user.id, stock_symbol='ABC', quantity=20, price=15, order_type='sell', status=OrderStatus.ACCEPTED.value, filled_qty=0)
    db.add(order)
    db.commit();
    # Fill 10
    apply_fill(db, order.id, 10, 15)
    db.commit(); db.refresh(order); db.refresh(h); db.refresh(user)
    assert order.status == OrderStatus.PARTIALLY_FILLED.value
    assert h.reserved_qty == 10
    # Cancel remaining
    apply_cancel(db, order.id, OrderStatus.CANCELLED.value)
    db.commit(); db.refresh(order); db.refresh(h)
    assert order.status == OrderStatus.CANCELLED.value
    assert h.reserved_qty == 0
    # Funds credit audit should exist
    audits = db.query(AuditLog).all()
    assert any(a.action=='FUNDS_CREDIT' for a in audits)
    assert any(a.action=='ORDER_CANCELLED' or a.action=='ORDER_CANCELLED' for a in audits)
