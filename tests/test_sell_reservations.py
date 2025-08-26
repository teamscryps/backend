import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base
from models.user import User
from models.order import Order
from models.holding import Holding
from services.fills import apply_fill, apply_cancel

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setup():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def make_user(db, funds=5000):
    u = User(name='Trader', email=f's{funds}@e.com', password='x', mobile='1', broker='zerodha', session_id='sess', role='client', cash_available=funds, cash_blocked=0)
    db.add(u); db.commit(); db.refresh(u); return u


def test_sell_reservation_and_fill():
    db = TestingSessionLocal()
    user = make_user(db)
    h = Holding(user_id=user.id, symbol='ABC', quantity=50, avg_price=100.0, reserved_qty=0)
    db.add(h); db.commit()
    # place sell order (simulate reservation)
    order = Order(user_id=user.id, stock_symbol='ABC', quantity=20, price=110, order_type='sell', status='ACCEPTED')
    db.add(order); db.commit()
    # Manually reserve like endpoint would
    h.reserved_qty += 20; db.commit(); db.refresh(h)
    assert h.quantity == 50 and h.reserved_qty == 20
    # Apply fill of 5
    apply_fill(db, order.id, 5, 110.0, broker_fill_id='SF1'); db.commit(); db.refresh(h); db.refresh(order); db.refresh(user)
    assert h.quantity == 45  # reduced by 5
    assert h.reserved_qty == 15
    cash_after_first = float(user.cash_available)
    # Apply remaining 15
    apply_fill(db, order.id, 15, 111.0, broker_fill_id='SF2'); db.commit(); db.refresh(h); db.refresh(order); db.refresh(user)
    assert h.quantity == 30
    assert h.reserved_qty == 0
    assert order.status == 'FILLED'
    # Funds credited appropriately
    assert float(user.cash_available) > cash_after_first


def test_sell_cancel_releases_reserved():
    db = TestingSessionLocal()
    user = make_user(db)
    h = Holding(user_id=user.id, symbol='XYZ', quantity=40, avg_price=90.0, reserved_qty=0)
    db.add(h); db.commit()
    order = Order(user_id=user.id, stock_symbol='XYZ', quantity=30, price=95, order_type='sell', status='ACCEPTED')
    db.add(order); db.commit()
    h.reserved_qty += 30; db.commit(); db.refresh(h)
    assert h.reserved_qty == 30
    # cancel
    apply_cancel(db, order.id, 'CANCELLED'); db.commit(); db.refresh(h); db.refresh(order)
    assert h.reserved_qty == 0
    assert order.status == 'CANCELLED'
