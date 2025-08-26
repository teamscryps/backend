"""Pure SQLAlchemy unit tests for holdings logic without FastAPI app imports.

These mirror the logic implemented in endpoints/trade.py & endpoints/trader.py.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from database import Base
from models.user import User
from models.holding import Holding
from services.holdings import (
    apply_buy, apply_sell, validate_sell, InsufficientHoldingsError,
    apply_buy_with_funds, apply_sell_with_funds, InsufficientFundsError
)
import math

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def make_user(db, email="u1@example.com"):
    u = User(name="Test User", email=email, password="x", mobile="123", api_key="k", api_secret="s", broker="zerodha", session_id="sess", role="client", cash_available=100000, cash_blocked=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_buy_increases_qty_and_sets_avg(db):
    user = make_user(db)
    assert db.query(Holding).count() == 0
    apply_buy(db, user.id, "INFY", 10, 100.0)
    db.commit()
    h = db.query(Holding).filter_by(user_id=user.id, symbol="INFY").first()
    assert h.quantity == 10
    assert h.avg_price == 100.0


def test_consecutive_buys_weighted_average(db):
    user = make_user(db)
    apply_buy(db, user.id, "TCS", 10, 100.0)
    apply_buy(db, user.id, "TCS", 20, 130.0)
    db.commit()
    h2 = db.query(Holding).filter_by(user_id=user.id, symbol="TCS").first()
    assert h2.quantity == 30
    assert abs(h2.avg_price - 120.0) < 1e-6


def test_sell_decreases_qty(db):
    user = make_user(db)
    apply_buy(db, user.id, "RELIANCE", 50, 2500.0)
    apply_sell(db, user.id, "RELIANCE", 20)
    db.commit()
    h2 = db.query(Holding).filter_by(user_id=user.id, symbol="RELIANCE").first()
    assert h2.quantity == 30


def test_sell_to_zero_deletes_row(db):
    user = make_user(db)
    apply_buy(db, user.id, "SBIN", 15, 600.0)
    apply_sell(db, user.id, "SBIN", 15)
    db.commit()
    assert db.query(Holding).filter_by(user_id=user.id, symbol="SBIN").first() is None


def test_oversell_rejected(db):
    user = make_user(db)
    apply_buy(db, user.id, "ITC", 5, 450.0)
    db.commit()
    with pytest.raises(InsufficientHoldingsError):
        validate_sell(db, user.id, "ITC", 10)


def test_zero_price_buy_rejected(db):
    user = make_user(db)
    with pytest.raises(ValueError):
        apply_buy(db, user.id, "ZERO", 10, 0.0)
    with pytest.raises(ValueError):
        apply_buy(db, user.id, "ZERO", 10, -5.0)


def test_large_quantity_buy(db):
    user = make_user(db)
    large_qty = 1_500_000
    apply_buy(db, user.id, "BIG", large_qty, 2.5)
    db.commit()
    h = db.query(Holding).filter_by(user_id=user.id, symbol="BIG").first()
    assert h.quantity == large_qty
    assert h.avg_price == 2.5


def test_fractional_price_weighted_average(db):
    user = make_user(db)
    apply_buy(db, user.id, "FRAC", 100, 123.45)
    apply_buy(db, user.id, "FRAC", 50, 123.55)
    db.commit()
    h = db.query(Holding).filter_by(user_id=user.id, symbol="FRAC").first()
    expected = (100*123.45 + 50*123.55) / 150
    assert h.quantity == 150
    assert math.isclose(h.avg_price, expected, rel_tol=1e-9, abs_tol=1e-9)


def test_full_liquidation_after_multiple_buys(db):
    user = make_user(db)
    apply_buy(db, user.id, "LIQ", 40, 10.0)
    apply_buy(db, user.id, "LIQ", 60, 12.0)
    # total qty now 100
    apply_sell(db, user.id, "LIQ", 25)
    apply_sell(db, user.id, "LIQ", 75)
    db.commit()
    assert db.query(Holding).filter_by(user_id=user.id, symbol="LIQ").first() is None


def test_buy_with_funds_deducts(db):
    user = make_user(db)
    starting = float(user.cash_available)
    apply_buy_with_funds(db, user, "FUND", 10, 10.0)
    db.commit()
    db.refresh(user)
    assert float(user.cash_available) == starting - 100
    h = db.query(Holding).filter_by(user_id=user.id, symbol="FUND").first()
    assert h and h.quantity == 10


def test_sell_with_funds_credits(db):
    user = make_user(db)
    apply_buy_with_funds(db, user, "CREDIT", 10, 5.0)
    db.commit()
    before = float(user.cash_available)
    apply_sell_with_funds(db, user, "CREDIT", 4, 5.0)
    db.commit()
    db.refresh(user)
    assert float(user.cash_available) == before + 20
    h = db.query(Holding).filter_by(user_id=user.id, symbol="CREDIT").first()
    assert h and h.quantity == 6


def test_insufficient_funds_buy(db):
    user = make_user(db)
    user.cash_available = 10
    db.commit()
    with pytest.raises(InsufficientFundsError):
        apply_buy_with_funds(db, user, "EXP", 5, 5.0)

