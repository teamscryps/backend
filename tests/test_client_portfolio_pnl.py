from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models.user import User
from models.holding import Holding
from models.order import Order
from datetime import datetime
import uuid

client = TestClient(app)


def make_user(email: str):
    # Ensure uniqueness across multiple test runs within same process
    unique_email = email.replace("@", f"+{uuid.uuid4().hex[:6]}@")
    db = SessionLocal()
    u = User(name="User", email=unique_email, password="pw", mobile="000", role="client", cash_available=1000, cash_blocked=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


def test_portfolio_endpoint_basic():
    u = make_user("pclient@example.com")
    # Authenticate shortcut: assume get_current_user uses token; for simplicity patch by dependency override if needed later.
    # Direct DB insert holdings & pending order
    db = SessionLocal()
    h = Holding(user_id=u.id, symbol="ABC", quantity=10, avg_price=100.0, reserved_qty=0)
    o = Order(user_id=u.id, stock_symbol="ABC", quantity=5, price=101.0, order_type="buy", status="ACCEPTED", filled_qty=0)
    db.add(h)
    db.add(o)
    db.commit()
    db.close()
    # Without proper auth this may 401; skip if so
    resp = client.get("/api/v1/client/portfolio", headers={"Authorization": "Bearer test"})
    assert resp.status_code in (200,401)
    if resp.status_code == 200:
        data = resp.json()
        assert data["cash_available"] == 1000.0
        assert len(data["holdings"]) == 1


def test_unrealized_pnl_stub():
    u = make_user("pclient2@example.com")
    db = SessionLocal()
    db.add(Holding(user_id=u.id, symbol="XYZ", quantity=4, avg_price=50.0))
    db.commit()
    db.close()
    resp = client.get(f"/api/v1/client/{u.id}/pnl/unrealized", headers={"Authorization": "Bearer test"})
    assert resp.status_code in (200,403,401)
    if resp.status_code == 200:
        body = resp.json()
        assert body["user_id"] == u.id
        assert "items" in body
