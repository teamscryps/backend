import os
os.environ["TEST_MODE"] = "1"
import os
os.environ["TEST_MODE"] = "1"
import pytest
import asyncio
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models.user import User
from models.trader_client import TraderClient
from models.order import Order
from models.holding import Holding
from services.holdings import get_holdings
from services.brokers.types import PlaceOrderRequest, PlaceOrderResult, OrderStatus, SessionStatus
from endpoints.trader import place_order_for_client, TraderOrderIn
import endpoints.trader as trader_ep

DATABASE_URL = "sqlite://"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def make_user(db, email, role, funds=100000, broker="zerodha"):
    u = User(name="User", email=email, password="pw", mobile="123", api_key="k", api_secret="s", broker=broker, session_id="sess", role=role, cash_available=Decimal(str(funds)), cash_blocked=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

class FakeAdapter:
    def __init__(self, user):
        self.user = user
    def ensure_session(self, user):
        return SessionStatus(ok=True)
    async def place_order(self, req: PlaceOrderRequest):
        return PlaceOrderResult(status=OrderStatus.ACCEPTED, broker_order_id="BRK1", placed_qty=req.quantity, filled_qty=0, avg_fill_price=None, raw={})

def patch_adapter(monkeypatch):
    import services.brokers.factory as factory
    monkeypatch.setattr(factory, "get_adapter", lambda user: FakeAdapter(user))
    monkeypatch.setattr(trader_ep, "get_adapter", lambda user: FakeAdapter(user))

def test_trader_buy_reserves_funds_no_holdings(monkeypatch):
    async def _run():
        db = SessionLocal()
        patch_adapter(monkeypatch)
        trader = make_user(db, "trader@example.com", "trader")
        client = make_user(db, "client1@example.com", "client", funds=5000)
        db.add(TraderClient(trader_id=trader.id, client_id=client.id))
        db.commit()
        assert get_holdings(db, client.id) == []
        payload = TraderOrderIn(stock_ticker="ABC", quantity=10, order_type="buy", type="eq", price=50.0)
        starting_cash = float(client.cash_available)
        await place_order_for_client(client.id, payload, current_user=trader, db=db)
        db.refresh(client)
        assert float(client.cash_blocked) == 500.0
        assert float(client.cash_available) == starting_cash - 500.0
        orders = db.query(Order).filter(Order.user_id == client.id).all()
        assert len(orders) == 1 and orders[0].stock_symbol == "ABC" and orders[0].filled_qty == 0
    asyncio.run(_run())

def test_trader_sell_existing_holding_no_cash_change(monkeypatch):
    async def _run():
        db = SessionLocal()
        patch_adapter(monkeypatch)
        trader = make_user(db, "trader2@example.com", "trader")
        client = make_user(db, "client2@example.com", "client", funds=10000)
        db.add(TraderClient(trader_id=trader.id, client_id=client.id))
        db.add(Holding(user_id=client.id, symbol="INFY", quantity=5, avg_price=100.0))
        db.commit()
        payload = TraderOrderIn(stock_ticker="INFY", quantity=2, order_type="sell", type="eq", price=110.0)
        await place_order_for_client(client.id, payload, current_user=trader, db=db)
        db.refresh(client)
        assert float(client.cash_available) == 10000
        assert float(client.cash_blocked) == 0
        order = db.query(Order).filter(Order.user_id==client.id).first()
        assert order and order.order_type=='sell' and order.filled_qty==0
    asyncio.run(_run())

def test_trader_insufficient_funds(monkeypatch):
    async def _run():
        db = SessionLocal()
        patch_adapter(monkeypatch)
        trader = make_user(db, "trader3@example.com", "trader")
        client = make_user(db, "client3@example.com", "client", funds=100)
        db.add(TraderClient(trader_id=trader.id, client_id=client.id))
        db.commit()
        payload = TraderOrderIn(stock_ticker="INFY", quantity=5, order_type="buy", type="eq", price=50.0)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await place_order_for_client(client.id, payload, current_user=trader, db=db)
        assert exc.value.status_code == 400
        assert "Insufficient available funds" in exc.value.detail
    asyncio.run(_run())

def test_trader_oversell(monkeypatch):
    async def _run():
        db = SessionLocal()
        patch_adapter(monkeypatch)
        trader = make_user(db, "trader4@example.com", "trader")
        client = make_user(db, "client4@example.com", "client", funds=10000)
        db.add(TraderClient(trader_id=trader.id, client_id=client.id))
        db.add(Holding(user_id=client.id, symbol="INFY", quantity=5, avg_price=100.0))
        db.commit()
        from fastapi import HTTPException
        payload = TraderOrderIn(stock_ticker="INFY", quantity=10, order_type="sell", type="eq", price=100.0)
        with pytest.raises(HTTPException) as exc:
            await place_order_for_client(client.id, payload, current_user=trader, db=db)
        assert exc.value.status_code == 400
        assert "Insufficient holdings" in exc.value.detail
    asyncio.run(_run())

def test_trader_broker_failure(monkeypatch):
    async def _run():
        # Simulate adapter raising session error -> HTTP 401
        db = SessionLocal()
        trader = make_user(db, "trader5@example.com", "trader")
        client = make_user(db, "client5@example.com", "client", funds=10000)
        db.add(TraderClient(trader_id=trader.id, client_id=client.id))
        db.commit()
        class FailAdapter:
            def __init__(self, user): self.user=user
            def ensure_session(self, user):
                return SessionStatus(ok=False, reason="bad session")
        import services.brokers.factory as factory
        monkeypatch.setattr(factory, "get_adapter", lambda user: FailAdapter(user))
        monkeypatch.setattr(trader_ep, "get_adapter", lambda user: FailAdapter(user))
        payload = TraderOrderIn(stock_ticker="INFY", quantity=2, order_type="buy", type="eq", price=100.0)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await place_order_for_client(client.id, payload, current_user=trader, db=db)
        assert exc.value.status_code == 401
        assert "session" in exc.value.detail.lower()
    asyncio.run(_run())
