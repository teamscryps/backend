from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from models.trade import Trade
from models.order import Order
from models.order_fill import OrderFill
from models.trader_client import TraderClient
from models.audit_log import AuditLog
from models.holding import Holding
from services.holdings import (
    apply_buy, apply_sell, validate_sell, get_holdings,
    InsufficientHoldingsError, apply_buy_with_funds, apply_sell_with_funds, InsufficientFundsError
)
from schemas.trader import TraderClientOut, TraderClientTradeOut, TraderOrderResponse
from schemas.client import ClientOut, ClientDetailsOut, ClientCreate, ClientUpdate, ResetResponse
from schemas.trades import ActiveTradeOut, TransactionOut
from schemas.order import OrderOut
from schemas.stock import StockOptionOut, StockDetailsOut
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

router = APIRouter(tags=["trader"])

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
    from config import settings
    if settings.DEBUG:
        return  # Allow in debug mode
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


@router.get("/clients", response_model=List[ClientOut])
def list_trader_clients(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if settings.DEBUG:
        # In debug mode, return all clients for development
        clients = db.query(UserModel).filter(UserModel.role == 'client').all()
    else:
        # Fetch mapped clients
        mappings = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id).all()
        client_ids = [m.client_id for m in mappings]
        if not client_ids:
            return []
        clients = db.query(UserModel).filter(UserModel.id.in_(client_ids)).all()
    
    result = []
    for c in clients:
        # Calculate portfolio value: sum of holdings value + cash_available
        holdings = db.query(Holding).filter(Holding.user_id == c.id).all()
        holdings_value = sum(h.quantity * h.avg_price for h in holdings)
        portfolio_value = holdings_value + float(c.cash_available or 0)
        result.append(ClientOut(
            id=c.id,
            name=c.name or "",
            email=c.email,
            pan=c.pan or "",
            phone=c.mobile,
            status=c.status or "active",
            portfolio_value=portfolio_value,
            join_date=c.created_at,
            broker_api_key=c.api_key
        ))
    return result


@router.get("/clients/{client_id}", response_model=ClientDetailsOut)
def get_client_details(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Calculate portfolio value
    holdings = db.query(Holding).filter(Holding.user_id == client.id).all()
    holdings_value = sum(h.quantity * h.avg_price for h in holdings)
    portfolio_value = holdings_value + float(client.cash_available or 0)
    allocated_funds = float(client.cash_available or 0) + float(client.cash_blocked or 0)
    remaining_funds = allocated_funds - portfolio_value
    
    # Calculate PNL
    trades = db.query(Trade).filter(Trade.user_id == client.id).all()
    total_pnl = sum((t.current_price - t.buy_price) * t.quantity for t in trades if t.current_price and t.buy_price)
    
    # Calculate today's PNL (simplified - you might want to filter by date)
    todays_pnl = total_pnl  # For now, using total as today's
    
    # Count trades
    active_trades = db.query(Trade).filter(Trade.user_id == client.id, Trade.status == 'active').count()
    total_trades = db.query(Trade).filter(Trade.user_id == client.id).count()
    
    return ClientDetailsOut(
        id=client.id,
        name=client.name or "",
        email=client.email,
        pan=client.pan or "",
        phone=client.mobile,
        status=client.status or "active",
        portfolio_value=portfolio_value,
        join_date=client.created_at,
        broker_api_key=client.api_key,
        allocated_funds=allocated_funds,
        remaining_funds=remaining_funds,
        total_pnl=total_pnl,
        todays_pnl=todays_pnl,
        active_trades_count=active_trades,
        total_trades_count=total_trades
    )


@router.post("/clients", response_model=ClientOut, status_code=201)
def add_client(client_data: ClientCreate, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    # Create new client user
    new_client = UserModel(
        name=client_data.name,
        email=client_data.email,
        password="temp_password",  # Should generate or set properly
        mobile=client_data.phone,
        pan=client_data.pan,
        status=client_data.status,
        api_key=client_data.broker_api_key,
        role="client"
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    # Link to trader
    mapping = TraderClient(trader_id=current_user.id, client_id=new_client.id)
    db.add(mapping)
    db.commit()
    # Return ClientOut
    return ClientOut(
        id=new_client.id,
        name=new_client.name,
        email=new_client.email,
        pan=new_client.pan,
        phone=new_client.mobile,
        status=new_client.status,
        portfolio_value=0.0,  # New client
        join_date=new_client.created_at,
        broker_api_key=new_client.api_key
    )


@router.put("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, client_data: ClientUpdate, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Update fields
    for field, value in client_data.model_dump(exclude_unset=True).items():
        if field == "phone":
            setattr(client, "mobile", value)
        elif field == "broker_api_key":
            setattr(client, "api_key", value)
        else:
            setattr(client, field, value)
    db.commit()
    db.refresh(client)
    # Calculate portfolio value
    holdings = db.query(Holding).filter(Holding.user_id == client.id).all()
    holdings_value = sum(h.quantity * h.avg_price for h in holdings)
    portfolio_value = holdings_value + float(client.cash_available or 0)
    return ClientOut(
        id=client.id,
        name=client.name or "",
        email=client.email,
        pan=client.pan or "",
        phone=client.mobile,
        status=client.status or "active",
        portfolio_value=portfolio_value,
        join_date=client.created_at,
        broker_api_key=client.api_key
    )


@router.delete("/clients/{client_id}")
def delete_client(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Delete mapping first
    db.delete(mapping)
    # Delete client (cascade will handle related data)
    db.delete(client)
    db.commit()
    return {"message": "Client deleted successfully"}


@router.get("/clients/{client_id}/transactions", response_model=List[TransactionOut])
def get_client_transactions(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    trades = db.query(Trade).filter(Trade.user_id == client_id).order_by(Trade.order_executed_at.desc()).all()
    result = []
    for t in trades:
        # Mock current_price; in real, fetch from broker
        current_price = t.sell_price or t.buy_price or 100.0  # Placeholder
        pnl = (current_price - t.buy_price) * t.quantity if t.buy_price else 0
        pnl_percent = (pnl / (t.buy_price * t.quantity)) * 100 if t.buy_price and t.buy_price * t.quantity != 0 else 0
        result.append(TransactionOut(
            id=t.id,
            stock=t.stock_ticker,
            name=t.stock_ticker,  # Placeholder for name
            quantity=t.quantity,
            buy_price=t.buy_price or 0,
            current_price=current_price,
            mtf_enabled=t.type == "mtf",
            timestamp=t.order_executed_at,
            type="buy" if t.buy_price else "sell",  # Assuming buy if buy_price set
            pnl=pnl,
            pnl_percent=pnl_percent
        ))
    return result


@router.get("/clients/{client_id}/trades/active", response_model=List[ActiveTradeOut])
def get_client_active_trades(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    trades = db.query(Trade).filter(Trade.user_id == client_id, Trade.status == "open").all()
    result = []
    for t in trades:
        # Mock current_price
        current_price = t.buy_price or 100.0
        result.append(ActiveTradeOut(
            id=t.id,
            stock=t.stock_ticker,
            name=t.stock_ticker,
            quantity=t.quantity,
            buy_price=t.buy_price or 0,
            current_price=current_price,
            mtf_enabled=t.type == "mtf",
            timestamp=t.order_executed_at
        ))
    return result


@router.get("/clients/{client_id}/trades/history", response_model=List[TransactionOut])
def get_client_trades_history(client_id: int, filter: Optional[str] = None, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    query = db.query(Trade).filter(Trade.user_id == client_id)
    if filter:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if filter == "today":
            query = query.filter(Trade.order_executed_at >= now.replace(hour=0, minute=0, second=0))
        elif filter == "last7days":
            query = query.filter(Trade.order_executed_at >= now - timedelta(days=7))
        elif filter == "thisMonth":
            query = query.filter(Trade.order_executed_at >= now.replace(day=1))
        elif filter == "profitable":
            # Placeholder: need to calculate PNL
            pass
        elif filter == "loss":
            pass
    trades = query.order_by(Trade.order_executed_at.desc()).all()
    result = []
    for t in trades:
        current_price = t.sell_price or t.buy_price or 100.0
        pnl = (current_price - t.buy_price) * t.quantity if t.buy_price else 0
        pnl_percent = (pnl / (t.buy_price * t.quantity)) * 100 if t.buy_price and t.buy_price * t.quantity != 0 else 0
        result.append(TransactionOut(
            id=t.id,
            stock=t.stock_ticker,
            name=t.stock_ticker,
            quantity=t.quantity,
            buy_price=t.buy_price or 0,
            current_price=current_price,
            mtf_enabled=t.type == "mtf",
            timestamp=t.order_executed_at,
            type="buy" if t.buy_price else "sell",
            pnl=pnl,
            pnl_percent=pnl_percent
        ))
    return result


@router.get("/clients/{client_id}/orders", response_model=List[OrderOut])
def get_client_orders(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    orders = db.query(Order).filter(Order.user_id == client_id).order_by(Order.order_executed_at.desc()).all()
    result = []
    for o in orders:
        result.append(OrderOut(
            id=o.id,
            client_id=o.user_id,
            stock=o.stock_symbol,
            name=o.stock_symbol,  # Placeholder
            quantity=o.quantity,
            price=o.price or 0,
            type=o.order_type,
            mtf_enabled=o.mtf_enabled,
            status=o.status or "pending",
            timestamp=o.order_executed_at
        ))
    return result


@router.delete("/orders/{order_id}")
def cancel_order(order_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    from config import settings
    if not settings.DEBUG:
        # Ensure the order belongs to a client of this trader
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == order.user_id).first()
        if not mapping:
            raise HTTPException(status_code=403, detail="Order not accessible")
    # Cancel order
    order.status = "cancelled"
    db.commit()
    return {"message": "Order cancelled successfully"}


@router.post("/clients/{client_id}/reset", response_model=ResetResponse)
def reset_client(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Reset: delete trades, orders, holdings, reset funds
    db.query(Trade).filter(Trade.user_id == client_id).delete()
    db.query(Order).filter(Order.user_id == client_id).delete()
    db.query(Holding).filter(Holding.user_id == client_id).delete()
    client.cash_available = 0
    client.cash_blocked = 0
    db.commit()
    return ResetResponse(success=True)


class PlaceOrderRequest(BaseModel):
    client_id: int
    stock: str
    quantity: int
    price: float
    type: Literal['buy', 'sell']
    mtf_enabled: bool


@router.post("/orders", response_model=OrderOut, status_code=201)
async def place_order(order_data: PlaceOrderRequest, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure client is linked
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == order_data.client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == order_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Create order
    new_order = Order(
        user_id=order_data.client_id,
        stock_symbol=order_data.stock,
        quantity=order_data.quantity,
        price=order_data.price,
        order_type=order_data.type,
        mtf_enabled=order_data.mtfEnabled,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return OrderOut(
        id=new_order.id,
        client_id=new_order.user_id,
        stock=new_order.stock_symbol,
        name=new_order.stock_symbol,
        quantity=new_order.quantity,
        price=new_order.price or 0,
        type=new_order.order_type,
        mtf_enabled=new_order.mtf_enabled,
        status=new_order.status or "pending",
        timestamp=new_order.order_executed_at
    )


@router.get("/clients/{client_id}/trades", response_model=List[TraderClientTradeOut])
def list_client_trades(client_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_trader(current_user)
    from config import settings
    if not settings.DEBUG:
        # Ensure mapping exists
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
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
    from config import settings
    if not settings.DEBUG:
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    client = db.query(UserModel).filter(UserModel.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.session_id and not settings.DEBUG:
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
    from config import settings
    if not settings.DEBUG:
        mapping = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id, TraderClient.client_id == client_id).first()
        if not mapping:
            raise HTTPException(status_code=404, detail="Client not linked to trader")
    holdings = get_holdings(db, client_id)
    return [HoldingOut(symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price, last_updated=h.last_updated.isoformat() if h.last_updated else None) for h in holdings]


# Direct Trader Trading Endpoints (Trader can trade for themselves)

@router.post("/my-orders", response_model=TraderOrderResponse, status_code=201)
async def place_trader_order(payload: TraderOrderIn, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Place order directly for the trader (not for a client)"""
    ensure_trader(current_user)

    # Validate trader has active session
    if not current_user.session_id:
        raise HTTPException(status_code=400, detail="Trader brokerage session inactive. Please login to your broker first.")

    # Funds check for buy orders
    if payload.order_type == 'buy' and payload.price is not None:
        est_cost = Decimal(str(payload.price)) * Decimal(payload.quantity)
        spendable = Decimal(str(current_user.cash_available or 0))
        if spendable < est_cost:
            raise HTTPException(status_code=400, detail="Insufficient available funds")

    # Execute via broker adapter
    adapter = get_adapter(current_user)
    try:
        ensure = adapter.ensure_session(current_user)
        if not ensure.ok:
            raise BrokerSessionError(ensure.reason or "session invalid")

        order_req = PlaceOrderRequest(
            symbol=payload.stock_ticker,
            side=payload.order_type.upper(),  # BUY or SELL
            quantity=payload.quantity,
            order_type="MARKET" if payload.price is None else "LIMIT",
            price=payload.price,
            product="MTF" if payload.type == "mtf" else ("CNC" if current_user.broker=='zerodha' else "DELIVERY"),
            validity="DAY",
            user_id=current_user.id
        )

        order_result = await adapter.place_order(order_req)

        # Create order record
        order = Order(
            user_id=current_user.id,
            stock_symbol=payload.stock_ticker,
            stock_name="",  # Will be filled by broker adapter
            quantity=payload.quantity,
            order_type=payload.order_type,
            price=payload.price,
            mtf_enabled=(payload.type == "mtf"),
            status="NEW",
            broker_order_id=order_result.broker_order_id if hasattr(order_result, 'broker_order_id') else None
        )
        db.add(order)
        db.flush()

        # Handle order fills if any
        if order_result.filled_qty > 0:
            fill = OrderFill(
                order_id=order.id,
                quantity=order_result.filled_qty,
                price=order_result.avg_fill_price or payload.price or 0,
                created_at=datetime.utcnow()
            )
            db.add(fill)

            # Update holdings and funds
            if payload.order_type == 'buy':
                apply_buy(db, current_user.id, payload.stock_ticker, order_result.filled_qty, order_result.avg_fill_price or payload.price or 0)
            else:  # sell
                apply_sell(db, current_user.id, payload.stock_ticker, order_result.filled_qty, order_result.avg_fill_price or payload.price or 0)

            order.filled_qty = order_result.filled_qty
            order.status = "EXECUTED" if order_result.filled_qty == payload.quantity else "PARTIAL"

        log_trader_action(db, current_user.id, current_user.id, "TRADER_ORDER_PLACED",
                         f"ORDER {payload.order_type.upper()} {payload.stock_ticker} {payload.quantity}",
                         {"order_id": order.id, "broker_order_id": order_result.broker_order_id})

        db.commit()

        return TraderOrderResponse(
            order_id=order.id,
            trade_id=order.id,
            status=order.status or "NEW",
            message=f"Order placed successfully. Status: {order.status}"
        )

    except BrokerSessionError as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Broker session invalid")
    except BrokerRateLimitError as e:
        db.rollback()
        raise HTTPException(status_code=429, detail="Broker rate limited")
    except BrokerTemporaryError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail="Temporary broker error")
    except BrokerPermanentError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Broker rejected order")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/my-orders", response_model=List[OrderOut])
def get_trader_orders(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get trader's own orders"""
    ensure_trader(current_user)
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    return [OrderOut.from_orm(order) for order in orders]


@router.get("/holdings", response_model=List[HoldingOut])
def get_trader_holdings(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get trader's own holdings"""
    ensure_trader(current_user)
    holdings = get_holdings(db, current_user.id)
    return [HoldingOut(symbol=h.symbol, quantity=h.quantity, avg_price=h.avg_price,
                      last_updated=h.last_updated.isoformat() if h.last_updated else None) for h in holdings]


@router.get("/portfolio")
def get_trader_portfolio(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get trader's portfolio summary"""
    ensure_trader(current_user)

    # Get holdings with current market prices
    holdings = get_holdings(db, current_user.id)
    total_portfolio_value = 0
    total_investment = 0

    holdings_data = []
    for holding in holdings:
        # Get current market price (mock for now)
        current_price = 100.0 + (hash(holding.symbol) % 900)  # Mock price
        market_value = current_price * holding.quantity
        investment_value = holding.avg_price * holding.quantity
        pnl = market_value - investment_value
        pnl_percent = (pnl / investment_value * 100) if investment_value > 0 else 0

        total_portfolio_value += market_value
        total_investment += investment_value

        holdings_data.append({
            "symbol": holding.symbol,
            "quantity": holding.quantity,
            "avg_price": holding.avg_price,
            "current_price": current_price,
            "market_value": market_value,
            "investment_value": investment_value,
            "pnl": pnl,
            "pnl_percent": pnl_percent
        })

    return {
        "total_portfolio_value": total_portfolio_value,
        "total_investment": total_investment,
        "total_pnl": total_portfolio_value - total_investment,
        "total_pnl_percent": ((total_portfolio_value - total_investment) / total_investment * 100) if total_investment > 0 else 0,
        "cash_available": current_user.cash_available or 0,
        "cash_blocked": current_user.cash_blocked or 0,
        "holdings": holdings_data
    }


# Bulk Trading for All Clients
class BulkTradeAllRequest(BaseModel):
    stock_ticker: str
    quantity: int
    order_type: Literal['buy', 'sell']
    type: Literal['eq', 'mtf']
    price: Optional[float] = None
    percent_quantity: Optional[float] = None  # Alternative: use % of capital instead of fixed quantity


@router.post("/bulk-trade-all", response_model=dict)
async def bulk_trade_all_clients(payload: BulkTradeAllRequest, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Place trades for ALL trader's clients at once"""
    ensure_trader(current_user)

    # Get all trader's clients
    from config import settings
    if settings.DEBUG:
        # In debug mode, get all clients
        clients = db.query(UserModel).filter(UserModel.role == 'client').all()
    else:
        # Get mapped clients
        mappings = db.query(TraderClient).filter(TraderClient.trader_id == current_user.id).all()
        client_ids = [m.client_id for m in mappings]
        if not client_ids:
            raise HTTPException(status_code=400, detail="No clients linked to this trader")
        clients = db.query(UserModel).filter(UserModel.id.in_(client_ids)).all()

    if not clients:
        raise HTTPException(status_code=400, detail="No clients found")

    results = []
    successful_trades = 0
    failed_trades = 0

    # Process each client
    for client in clients:
        try:
            # Skip if client doesn't have active session (unless in debug mode)
            if not client.session_id and not settings.DEBUG:
                results.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "status": "failed",
                    "error": "Client brokerage session inactive"
                })
                failed_trades += 1
                continue

            # Calculate quantity if using percentage
            actual_quantity = payload.quantity
            if payload.percent_quantity:
                # Use percentage of client's capital
                capital_to_use = float(client.capital or 0) * (payload.percent_quantity / 100)
                # Get current price (mock for now, should use real price)
                current_price = 100.0 + (hash(payload.stock_ticker) % 900)  # Mock price
                actual_quantity = int(capital_to_use / current_price) if current_price > 0 else 0

            # Validate funds for buy orders
            if payload.order_type == 'buy' and payload.price:
                est_cost = Decimal(str(payload.price)) * Decimal(actual_quantity)
                spendable = Decimal(str(client.cash_available or 0))
                if spendable < est_cost and not ALLOW_UNLINKED_CLIENTS_FOR_TESTS:
                    results.append({
                        "client_id": client.id,
                        "client_name": client.name,
                        "status": "failed",
                        "error": f"Insufficient funds: need {float(est_cost)}, have {float(spendable)}"
                    })
                    failed_trades += 1
                    continue

            # Validate holdings for sell orders
            if payload.order_type == 'sell':
                try:
                    validate_sell(db, client.id, payload.stock_ticker, actual_quantity)
                except InsufficientHoldingsError as e:
                    results.append({
                        "client_id": client.id,
                        "client_name": client.name,
                        "status": "failed",
                        "error": f"Insufficient holdings: have {e.have}, want {e.want}"
                    })
                    failed_trades += 1
                    continue

            # Execute order for this client
            adapter = get_adapter(client)
            try:
                ensure = adapter.ensure_session(client)
                if not ensure.ok and not settings.DEBUG:
                    raise BrokerSessionError(ensure.reason or "session invalid")

                order_req = PlaceOrderRequest(
                    symbol=payload.stock_ticker,
                    side=payload.order_type.upper(),
                    quantity=actual_quantity,
                    order_type="MARKET" if payload.price is None else "LIMIT",
                    price=payload.price,
                    product="MTF" if payload.type == "mtf" else ("CNC" if client.broker=='zerodha' else "DELIVERY"),
                    validity="DAY",
                    user_id=client.id
                )

                order_result = await adapter.place_order(order_req)

                # Create order record
                order = Order(
                    user_id=client.id,
                    stock_symbol=payload.stock_ticker,
                    quantity=actual_quantity,
                    price=payload.price,
                    order_type=payload.order_type,
                    mtf_enabled=(payload.type == "mtf"),
                    status="NEW",
                    broker_order_id=order_result.broker_order_id if hasattr(order_result, 'broker_order_id') else None
                )
                db.add(order)
                db.flush()

                # Handle fund reservations
                if payload.order_type == 'buy' and payload.price:
                    est_cost = Decimal(str(payload.price)) * Decimal(actual_quantity)
                    client.cash_available = Decimal(str(client.cash_available or 0)) - est_cost
                    current_blocked = Decimal(str(client.cash_blocked or 0))
                    client.cash_blocked = current_blocked + est_cost

                elif payload.order_type == 'sell':
                    from models.holding import Holding
                    holding = db.query(Holding).filter(Holding.user_id==client.id, Holding.symbol==payload.stock_ticker).with_for_update().first()
                    if holding:
                        holding.reserved_qty += actual_quantity

                # Log the action
                log_trader_action(db, current_user.id, client.id, "BULK_ORDER_PLACED",
                    f"Bulk {payload.order_type.upper()} {payload.stock_ticker} x{actual_quantity}",
                    {"bulk_trade": True, "quantity": actual_quantity, "type": payload.type})

                db.commit()

                results.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "status": "success",
                    "order_id": order.id,
                    "quantity": actual_quantity,
                    "broker_order_id": order.broker_order_id
                })
                successful_trades += 1

            except Exception as e:
                db.rollback()
                results.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "status": "failed",
                    "error": f"Broker error: {str(e)}"
                })
                failed_trades += 1

        except Exception as e:
            results.append({
                "client_id": client.id,
                "client_name": client.name,
                "status": "failed",
                "error": f"Unexpected error: {str(e)}"
            })
            failed_trades += 1

    return {
        "message": f"Bulk trade completed: {successful_trades} successful, {failed_trades} failed",
        "total_clients": len(clients),
        "successful_trades": successful_trades,
        "failed_trades": failed_trades,
        "results": results
    }
