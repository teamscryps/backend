import json, os
from fastapi.testclient import TestClient
from main import app
from config import settings
import hmac, hashlib
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from database import Base, get_db
import models.order  # ensure Order model registered
import models.holding  # ensure Holding model
import models.order_fill  # ensure OrderFill model
import models.audit_log  # ensure AuditLog model
from models.user import User

# Set up isolated in-memory DB schema for these tests
os.environ["TEST_MODE"] = "1"
engine = create_engine("sqlite:///./test_webhook.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)


def sign(body: bytes):
    return hmac.new(settings.BROKER_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


import uuid

def create_test_trader_and_client(db: Session):
    suffix = uuid.uuid4().hex[:8]
    # minimal user creation bypassing auth for tests
    trader = User(name="Trader", email=f"trader{suffix}@example.com", password="x", mobile="000", role="trader")
    client_user = User(name="Client", email=f"client{suffix}@example.com", password="x", mobile="000", role="user", cash_available=100000, cash_blocked=0)
    db.add(trader)
    db.add(client_user)
    db.commit()
    db.refresh(client_user)
    return client_user


def create_order_direct(db: Session, user_id: int):
    from models.order import Order
    # ensure tables exist (idempotent)
    try:
        db.execute("SELECT 1 FROM orders LIMIT 1")
    except Exception:
        Base.metadata.create_all(bind=engine)
    o = Order(user_id=user_id, stock_symbol="TEST", quantity=10, price=100, order_type="buy", status="ACCEPTED")
    db.add(o)
    db.commit()
    db.refresh(o)
    return o.id


def test_fill_webhook_signature_and_idempotent_duplicate():
    # apply scoped override
    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    user = create_test_trader_and_client(db)
    order_id = create_order_direct(db, user.id)

    fill_body = json.dumps({"order_id": order_id, "quantity": 5, "price": 100.0, "broker_fill_id": "f1"}).encode()
    sig = sign(fill_body)
    headers = {"X-Broker-Signature": sig, "X-Broker-Signature-Alg": "HMAC-SHA256"}
    r1 = client.post("/api/v1/broker/fill", data=fill_body, headers=headers)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/v1/broker/fill", data=fill_body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "IGNORED"

    # Invalid signature
    bad_headers = {"X-Broker-Signature": "deadbeef"}
    r_bad = client.post("/api/v1/broker/fill", data=fill_body, headers=bad_headers)
    assert r_bad.status_code == 401
    app.dependency_overrides = original


def test_cancel_webhook_idempotent_and_signature():
    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    user = create_test_trader_and_client(db)
    order_id = create_order_direct(db, user.id)

    cancel_body = json.dumps({"order_id": order_id, "status": "CANCELLED"}).encode()
    sig = sign(cancel_body)
    headers = {"X-Broker-Signature": sig, "X-Broker-Signature-Alg": "HMAC-SHA256"}
    r1 = client.post("/api/v1/broker/cancel", data=cancel_body, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "CANCELLED"
    r2 = client.post("/api/v1/broker/cancel", data=cancel_body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["idempotent"] is True
    # Bad signature
    bad_headers = {"X-Broker-Signature": "bad"}
    r_bad = client.post("/api/v1/broker/cancel", data=cancel_body, headers=bad_headers)
    assert r_bad.status_code == 401
    app.dependency_overrides = original
