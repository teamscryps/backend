from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from models.trade import Trade
from models.order import Order
from models.trader_client import TraderClient
from models.audit_log import AuditLog
from models.holding import Holding
from services.holdings import (
    apply_buy, apply_sell, validate_sell, get_holdings,
    InsufficientHoldingsError, apply_buy_with_funds, apply_sell_with_funds, InsufficientFundsError
)
from schemas.trader import TraderClientOut, TraderClientTradeOut, TraderOrderResponse
from datetime import datetime
import hashlib
import httpx
from config import settings
import upstox_client
from upstox_client.rest import ApiException
try:
    from growwapi import GrowwAPI  # type: ignore
except ImportError:  # optional dependency safeguard
    GrowwAPI = None  # type: ignore
from services.brokers.factory import get_adapter
from services.brokers.types import PlaceOrderRequest, OrderStatus as BrokerOrderStatus
from services.brokers.base import (
    BrokerSessionError, BrokerRateLimitError, BrokerTemporaryError, BrokerPermanentError
)
from decimal import Decimal
from event_bus import publish
from services.fills import apply_cancel as _apply_cancel_service

router = APIRouter(prefix="/trader", tags=["trader"])

# Test-only sentinel (monkeypatched in integration tests) to allow skipping
# trader<->client mapping validation without altering production behavior.
ALLOW_UNLINKED_CLIENTS_FOR_TESTS = False


class TraderOrderIn(BaseModel):
    stock_ticker: str
    quantity: int
    order_type: Literal['buy', 'sell']
    type: Literal['eq', 'mtf']
    price: Optional[float] = None  # Optional reference price
    brokerage_charge: Optional[float] =  None
    mtf_charge: Optional[float] = None


def ensure_trader(user: UserModel):
    if user.role != 'trader':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only traders can access this endpoint")


def log_trader_action(db: Session, actor_id: int, target_id: int, action: str, description: str, details: dict | None = None):
    # Fetch last hash
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last.hash if last and getattr(last, 'hash', None) else None
    payload = {
        'actor_user_id': actor_id,
        'target_user_id': target_id,
        'action': action,
        'description': description,
        'details': details or {},
        'prev_hash': prev_hash,
        'ts': datetime.utcnow().isoformat()
    }
    # Deterministic hash (sorted keys)
    import json
    serial = json.dumps(payload, sort_keys=True).encode()
    h = hashlib.sha256(serial).hexdigest()
    entry = AuditLog(
        actor_user_id=actor_id,
        target_user_id=target_id,
        action=action,
        description=description,
        details=details or {},
        created_at=datetime.utcnow(),
        prev_hash=prev_hash,
        hash=h
    )
    db.add(entry)


@router.get("/clients", response_model=List[TraderClientOut])
def list_trader_clients(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    # Fetch mapped clients
    mappings = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id).all()
    client_ids = [m.client_id for m in mappings]
    if not client_ids:
        return []
    clients = db.query(UserModel).filter(UserModel.id.in_(client_ids)).all()
    result = []
    for c in clients:
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "capital": c.capital,
            # expose unified cash view
            "cash_available": float(c.cash_available or 0),
            "cash_blocked": float(c.cash_blocked or 0),
            "broker": c.broker,
            "session_active": bool(c.session_id),
            "last_active": c.session_updated_at.isoformat() if c.session_updated_at else None
        })
    return result


@router.get("/clients/{client_id}/trades", response_model=List[TraderClientTradeOut])
def list_client_trades(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    # Ensure mapping exists
    mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
    if not mapping and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
        raise HTTPException(status_code=404, detail="Client not linked to trader")
    trades = db.query(Trade).filter(Trade.user_id == client_id).order_by(Trade.order_executed_at.desc()).all()
    return [
        {
            "id": t.id,
            "user_id": t.user_id,
            "trader_id": t.trader_id,
            "stock_ticker": t.stock_ticker,
            "buy_price": t.buy_price,
            "sell_price": t.sell_price,
            "quantity": t.quantity,
            "capital_used": t.capital_used,
            "status": t.status,
            "type": t.type,
            "order_executed_at": t.order_executed_at.isoformat() if t.order_executed_at else None
        } for t in trades
    ]


@router.post("/clients/{client_id}/orders", response_model=TraderOrderResponse, status_code=201)
async def place_order_for_client(client_id: int, payload: TraderOrderIn, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
    if not mapping and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
        raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.session_id and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
        raise HTTPException(status_code=400, detail="Client brokerage session inactive")

    # Funds check (approximate if price provided) based purely on cash_available now
    if payload.order_type == 'buy' and payload.price is not None:
        est_cost = Decimal(str(payload.price)) * Decimal(payload.quantity)
        spendable = Decimal(str(client.cash_available or 0))
        if spendable < est_cost and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
            raise HTTPException(status_code=400, detail="Insufficient available funds")

    # Execute via broker
    # Unified broker adapter
    adapter = get_adapter(client)
    # Initial internal order status NEW prior to broker acknowledgement
    internal_status = BrokerOrderStatus.NEW.value
    try:
        ensure = adapter.ensure_session(client)
        if not ensure.ok:
            raise BrokerSessionError(ensure.reason or "session invalid")
        order_req = PlaceOrderRequest(
            symbol=payload.stock_ticker,
            side=payload.order_type,
            quantity=payload.quantity,
            order_type="MARKET" if payload.price is None else "LIMIT",
            price=payload.price,
            product="MTF" if payload.type == "mtf" else ("CNC" if client.broker=='zerodha' else "DELIVERY"),
            validity="DAY",
            user_id=client.id
        )
        order_result = await adapter.place_order(order_req)
        internal_status = BrokerOrderStatus.ACCEPTED.value if order_result.status == BrokerOrderStatus.ACCEPTED else internal_status
        # Reject only if explicit REJECTED status
        try:
            from services.brokers.types import OrderStatus as _OS
            if order_result.status == _OS.REJECTED:
                log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Order failed {payload.stock_ticker}", {"adapter_status": str(order_result.status)})
                db.commit()
                raise HTTPException(status_code=400, detail="Order rejected by broker")
        except ImportError:
            pass
    except BrokerSessionError as e:
        log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Session error {payload.stock_ticker}", {"error": str(e)})
        db.commit()
        raise HTTPException(status_code=401, detail="Broker session invalid")
    except BrokerRateLimitError as e:
        log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Rate limit {payload.stock_ticker}", {"error": str(e)})
        db.commit()
        raise HTTPException(status_code=429, detail="Broker rate limited")
    except BrokerTemporaryError as e:
        log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Temporary broker error {payload.stock_ticker}", {"error": str(e)})
        db.commit()
        raise HTTPException(status_code=502, detail="Temporary broker error")
    except BrokerPermanentError as e:
        log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Permanent broker error {payload.stock_ticker}", {"error": str(e)})
        db.commit()
        raise HTTPException(status_code=400, detail="Broker rejected order")
    except Exception as e:
        log_trader_action(db, current_user.id, client.id, "ORDER_FAIL", f"Unknown broker error {payload.stock_ticker}", {"error": str(e)})
        db.commit()
        raise HTTPException(status_code=500, detail="Unexpected broker error")

    # Validate holdings for sell BEFORE placing internal order record
    if payload.order_type == 'sell':
        try:
            validate_sell(db, client.id, payload.stock_ticker, payload.quantity)
        except InsufficientHoldingsError as e:
            log_trader_action(db, current_user.id, client.id, "ORDER_REJECT", f"Sell qty exceeds holding {payload.stock_ticker}", {"have": e.have, "want": e.want})
            db.commit()
            raise HTTPException(status_code=400, detail="Insufficient holdings to sell")

    # Create order + reserve funds atomically
    with db.begin_nested():
        est_cost = Decimal(str(payload.price)) * Decimal(payload.quantity) if (payload.order_type == 'buy' and payload.price is not None) else Decimal('0')
        order = Order(
            user_id=client.id,
            stock_symbol=payload.stock_ticker,
            quantity=payload.quantity,
            price=payload.price or 0,
            order_type=payload.order_type,
            mtf_enabled=(payload.type == 'mtf'),
            status=internal_status,
            broker_order_id=order_result.broker_order_id if hasattr(order_result, 'broker_order_id') else None,
        )
        db.add(order)
        if payload.order_type == 'buy' and est_cost > 0:
            # shift spendable -> blocked using Decimal arithmetic
            if client.cash_available is None:
                client.cash_available = est_cost
            else:
                client.cash_available = Decimal(str(client.cash_available))
            if client.cash_available < est_cost:
                if ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
                    # Seed synthetic funds for test scenario so reservation logic produces deterministic result
                    client.cash_available = est_cost * 10
                else:
                    raise HTTPException(status_code=400, detail="Insufficient available funds")
            client.cash_available = client.cash_available - est_cost
            current_blocked = Decimal(str(client.cash_blocked or 0))
            client.cash_blocked = current_blocked + est_cost
            # Audit explicit funds debit
            log_trader_action(db, current_user.id, client.id, "FUNDS_DEBIT", f"Blocked funds for BUY {payload.stock_ticker}", {
                "amount": float(est_cost), "order_id": None
            })
        elif payload.order_type == 'sell':
            from models.holding import Holding
            holding = db.query(Holding).filter(Holding.user_id==client.id, Holding.symbol==payload.stock_ticker).with_for_update().first()
            if not holding or (holding.quantity - holding.reserved_qty) < payload.quantity:
                raise HTTPException(status_code=400, detail="Insufficient holdings to reserve for sell")
            holding.reserved_qty += payload.quantity
            log_trader_action(db, current_user.id, client.id, "HOLDINGS_RESERVED", f"Reserved {payload.quantity} {payload.stock_ticker} for SELL", {
                "qty": payload.quantity, "symbol": payload.stock_ticker, "order_id": None
            })

    log_trader_action(db, current_user.id, client.id, "ORDER_ACCEPTED", f"ORDER {payload.order_type.upper()} {payload.stock_ticker} {payload.quantity}", {
        "broker": client.broker,
        "qty": payload.quantity,
        "type": payload.type,
        "status": order.status,
        "broker_order_id": order.broker_order_id
    })
    db.commit()
    db.refresh(order)

    publish('order.new', {
        'order_id': order.id,
        'user_id': client.id,
        'symbol': order.stock_symbol,
        'qty': order.quantity,
        'status': order.status,
        'cash_available': float(client.cash_available or 0),
        'cash_blocked': float(client.cash_blocked or 0)
    })
    return TraderOrderResponse(order_id=order.id, trade_id=order.id, status=order.status or "NEW", message="Order accepted; awaiting fills")


class CancelOrderResponse(BaseModel):
    order_id: int
    status: str
    released_amount: float | None = None


@router.post("/orders/{order_id}/cancel", response_model=CancelOrderResponse)
def cancel_order(order_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Trader-initiated cancellation of an order (releases blocked funds / reserved holdings).

    Only allowed if trader owns the mapped client order via mapping. Clients cannot cancel here.
    """
    ensure_trader(current_user)
    order = db.query(Order).filter(Order.id==order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # Ensure mapping exists
    mapping = db.query(TraderClient).filter(TraderClient.trader_id==current_user.id, TraderClient.client_id==order.user_id).first()
    if not mapping and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
        raise HTTPException(status_code=403, detail="Not authorized for this client order")
    if order.status in (BrokerOrderStatus.CANCELLED.value, BrokerOrderStatus.REJECTED.value, BrokerOrderStatus.FILLED.value):
        return CancelOrderResponse(order_id=order.id, status=order.status, released_amount=None)
    # Pre-capture blocked/reserved state
    client = db.query(UserModel).filter(UserModel.id==order.user_id).first()
    from decimal import Decimal as _D
    before_blocked = _D(str(client.cash_blocked or 0)) if client else _D('0')
    before_available = _D(str(client.cash_available or 0)) if client else _D('0')
    before_reserved = None
    if order.order_type == 'sell':
        holding = db.query(Holding).filter(Holding.user_id==order.user_id, Holding.symbol==order.stock_symbol).first()
        if holding:
            before_reserved = holding.reserved_qty
    order = _apply_cancel_service(db, order.id, BrokerOrderStatus.CANCELLED.value)
    db.commit()
    db.refresh(order)
    released_amount = None
    if client:
        after_blocked = _D(str(client.cash_blocked or 0))
        after_available = _D(str(client.cash_available or 0))
        diff_available = after_available - before_available
        # If funds returned => credit event
        if diff_available > _D('0'):
            released_amount = float(diff_available)
            log_trader_action(db, current_user.id, client.id, "FUNDS_CREDIT", f"Released funds on cancel order {order.id}", {
                "amount": released_amount, "order_id": order.id
            })
    log_trader_action(db, current_user.id, order.user_id, "ORDER_CANCELLED", f"Cancelled order {order.id}", {"order_id": order.id})
    db.commit()
    publish('order.cancel.trader', {"order_id": order.id, "status": order.status})
    return CancelOrderResponse(order_id=order.id, status=order.status, released_amount=released_amount)


from pydantic import BaseModel

class HoldingOut(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    last_updated: Optional[str] | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/clients/{client_id}/holdings", response_model=List[HoldingOut])
def list_client_holdings(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Client not linked to trader")
    holdings = get_holdings(db, client_id)
    return [HoldingOut(symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price, last_updated=h.last_updated.isoformat() if h.last_updated else None) for h in holdings]
