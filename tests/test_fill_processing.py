import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base
from models.user import User
from models.order import Order
from models.holding import Holding
from services.fills import apply_fill, apply_cancel, FillAlreadyApplied

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setup():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def make_user(db, funds=10000):
    u = User(name='U', email=f'u{funds}@e.com', password='x', mobile='1', broker='zerodha', session_id='sess', role='client', cash_available=funds, cash_blocked=0)
    db.add(u); db.commit(); db.refresh(u); return u


def test_partial_then_full_fill_buy():
    db = TestingSessionLocal()
    user = make_user(db)
    # create order as if reserved
    order = Order(user_id=user.id, stock_symbol='ABC', quantity=100, price=100, order_type='buy', mtf_enabled=False, status='ACCEPTED', broker_order_id='B1')
    db.add(order)
    user.cash_available = Decimal(str(user.cash_available)) - Decimal('100') * Decimal('100')
    user.cash_blocked = Decimal('100') * Decimal('100')
    db.commit(); db.refresh(user); db.refresh(order)

    apply_fill(db, order.id, 40, 99.0, broker_fill_id='F1')
    db.refresh(order); db.refresh(user)
    assert order.filled_qty == 40
    assert float(order.avg_fill_price) == pytest.approx(99.0)
    holding = db.query(Holding).filter_by(user_id=user.id, symbol='ABC').first()
    assert holding and holding.quantity == 40
    blocked_after_first = float(user.cash_blocked)

    apply_fill(db, order.id, 60, 98.0, broker_fill_id='F2')
    db.refresh(order); db.refresh(user); db.refresh(holding)
    assert order.filled_qty == 100
    assert order.status == 'FILLED'
    assert float(order.avg_fill_price) == pytest.approx((40*99 + 60*98)/100, rel=1e-4)
    assert holding.quantity == 100
    assert float(user.cash_blocked) <= 0.0001
    # Total debited equals executed average cost; initial funds 10000
    executed_cost = float(order.avg_fill_price) * 100  # should be 9840
    total_reserved = 100 * 100  # 10000
    refund = total_reserved - executed_cost  # 160
    # cash_available path: start 10000 -> reserve 10000 (available=0, blocked=10000) -> execute cost 10160 -> leftover blocked  - refunded at completion
    # leftover = refund = total_reserved - executed_cost
    assert float(user.cash_available) == pytest.approx(refund, rel=1e-4)


def test_idempotent_fill():
    db = TestingSessionLocal()
    user = make_user(db)
    order = Order(user_id=user.id, stock_symbol='XYZ', quantity=10, price=10, order_type='buy', status='ACCEPTED')
    db.add(order)
    user.cash_available = Decimal(str(user.cash_available)) - Decimal('100')
    user.cash_blocked = Decimal('100')
    db.commit()

    apply_fill(db, order.id, 5, 10.0, broker_fill_id='AF1')
    with pytest.raises(FillAlreadyApplied):
        apply_fill(db, order.id, 5, 10.0, broker_fill_id='AF1')


def test_cancel_releases_blocked():
    db = TestingSessionLocal()
    user = make_user(db)
    order = Order(user_id=user.id, stock_symbol='CAN', quantity=20, price=50, order_type='buy', status='ACCEPTED')
    db.add(order)
    user.cash_available = Decimal(str(user.cash_available)) - Decimal('1000')
    user.cash_blocked = Decimal('1000')
    db.commit()
    apply_cancel(db, order.id, 'CANCELLED')
    db.refresh(user); db.refresh(order)
    assert order.status == 'CANCELLED'
    assert float(user.cash_blocked) == 0
    assert float(user.cash_available) == 10000


def test_sell_fill_credits_cash():
    db = TestingSessionLocal()
    user = make_user(db)
    # seed holding
    h = Holding(user_id=user.id, symbol='S', quantity=50, avg_price=80)
    db.add(h)
    order = Order(user_id=user.id, stock_symbol='S', quantity=20, price=90, order_type='sell', status='ACCEPTED')
    db.add(order)
    db.commit()
    apply_fill(db, order.id, 20, 90.0, broker_fill_id='SF1')
    db.refresh(user); db.refresh(order); db.refresh(h)
    assert order.status == 'FILLED'
    assert h.quantity == 30
    assert float(user.cash_available) == pytest.approx(10000 + 20*90)
