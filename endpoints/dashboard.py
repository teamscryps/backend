
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload
from typing import List, Dict, Any
from database import get_db
from schemas.trades import TradeOut
from schemas.user import User
from schemas.order import OrderOut
from models.trade import Trade
from models.order import Order
from models.user import User as UserModel
from auth_service import get_user_by_email
from security import get_current_user
from datetime import datetime, timedelta
import httpx
from cryptography.fernet import Fernet
from config import settings
from pydantic import BaseModel, HttpUrl, validator
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
import json
from endpoints.logs import log_action, log_error, log_request

# Initialize Fernet for encryption
fernet = Fernet(settings.ENCRYPTION_KEY)

# Initialize Redis for rate limiting and caching
redis_client = redis.from_url(settings.REDIS_URL)

# Initialize rate limiter
async def init_rate_limiter():
    await FastAPILimiter.init(redis_client)

router = APIRouter(dependencies=[Depends(init_rate_limiter)])

# Pydantic schemas
class BrokerageActivation(BaseModel):
    brokerage: str
    api_url: str
    api_key: str
    api_secret: str
    request_token: str | None = None

    @validator("brokerage")
    def validate_brokerage(cls, v):
        valid_brokerages = ["zerodha", "groww"]
        if v.lower() not in valid_brokerages:
            raise ValueError("Invalid brokerage")
        return v.lower()

class OrderRequest(BaseModel):
    stock_ticker: str
    quantity: int
    price: float
    order_type: str  # "buy" or "sell"

async def refresh_zerodha_session(user: UserModel, db: Session, request: Request, correlation_id: str) -> str:
    """
    Refresh Zerodha session using the refresh_token.
    Returns the new access_token.
    """
    log_action("start_refresh_zerodha_session", user, correlation_id, {"broker": "zerodha"})
    if not user.broker_refresh_token:
        log_error("missing_refresh_token", Exception("No refresh token available"), user, correlation_id, {"broker": "zerodha"})
        raise HTTPException(status_code=400, detail="No refresh token available")

    decrypted_refresh_token = fernet.decrypt(user.broker_refresh_token.encode()).decode()
    decrypted_api_key = fernet.decrypt(user.api_key.encode()).decode()
    decrypted_api_secret = fernet.decrypt(user.api_secret.encode()).decode()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.kite.trade/session/refresh_token",
                data={
                    "api_key": decrypted_api_key,
                    "refresh_token": decrypted_refresh_token,
                    "checksum": generate_zerodha_checksum(decrypted_api_key, decrypted_refresh_token, decrypted_api_secret)
                },
                timeout=10
            )
            if response.status_code != 200:
                log_error("zerodha_session_refresh_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                raise HTTPException(status_code=400, detail="Failed to refresh Zerodha session")
            session_data = response.json()
            new_access_token = session_data.get("data", {}).get("access_token")
            if not new_access_token:
                log_error("no_access_token", Exception("No access token received"), user, correlation_id, {"broker": "zerodha"})
                raise HTTPException(status_code=400, detail="No access token received from Zerodha")

            # Update user with new encrypted access token
            user.session_id = fernet.encrypt(new_access_token.encode()).decode()
            user.session_updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            log_action("zerodha_session_refreshed", user, correlation_id, {"broker": "zerodha"})
            return new_access_token
        except httpx.RequestError as e:
            log_error("zerodha_refresh_api_error", e, user, correlation_id, {"broker": "zerodha"})
            raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

# Dashboard Data Endpoint
@router.get(
    "/dashboard",
    response_model=dict,
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def get_dashboard_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), request: Request = None):
    """
    Fetch all data required for the dashboard, including trades, portfolio, and funds.
    """
    correlation_id = await log_request(request, "fetch_dashboard_data", current_user)
    try:
        # Fetch user with eager loading
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        # Validate brokerage session
        if user.session_id and user.broker == "zerodha":
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.kite.trade/portfolio/holdings",
                        headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                        timeout=5
                    )
                    if response.status_code == 401:
                        log_action("attempt_zerodha_session_refresh", user, correlation_id, {"broker": "zerodha"})
                        # Attempt to refresh session
                        new_access_token = await refresh_zerodha_session(user, db, request, correlation_id)
                        # Retry holdings request with new token
                        response = await client.get(
                            "https://api.kite.trade/portfolio/holdings",
                            headers={"Authorization": f"token {new_access_token}"},
                            timeout=5
                        )
                        if response.status_code != 200:
                            log_error("zerodha_holdings_fetch_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                            raise HTTPException(status_code=401, detail="Failed to validate Zerodha session")
                except httpx.RequestError as e:
                    log_error("zerodha_api_error", e, user, correlation_id, {"broker": "zerodha"})
                    raise HTTPException(status_code=503, detail="Brokerage service unavailable")

        # Fetch ongoing trades
        ongoing_trades = db.query(Trade).options(
            selectinload(Trade.order)
        ).filter(
            Trade.status == 'open',
            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=30)
        ).all()

        # Fetch recent trades
        recent_trades = db.query(Trade).options(
            selectinload(Trade.order)
        ).filter(
            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(Trade.order_executed_at.desc()).limit(10).all()

        # Fetch upcoming trades
        upcoming_trades = db.query(Order).filter(
            Order.user_id == user.id,
            Order.order_type == "buy"
        ).all()

        # Fetch funds from Zerodha (if active)
        unused_funds = 2300  # Placeholder
        allocated_funds = 0
        if user.broker == "zerodha" and user.session_id:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.kite.trade/user/margins",
                        headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                        timeout=5
                    )
                    if response.status_code == 200:
                        margins = response.json().get("data", {}).get("equity", {})
                        unused_funds = margins.get("available", {}).get("cash", 0)
                        allocated_funds = margins.get("utilised", {}).get("debits", 0)
                    else:
                        log_error("zerodha_margins_fetch_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                except httpx.RequestError as e:
                    log_error("zerodha_margins_api_error", e, user, correlation_id, {"broker": "zerodha"})

        # Calculate portfolio overview
        total_invested = sum(trade.capital_used for trade in ongoing_trades)
        total_profit = sum(
            (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
            for trade in recent_trades if trade.sell_price
        )
        portfolio_value = total_invested + total_profit
        portfolio_change = (total_profit / total_invested * 100) if total_invested > 0 else 0

        # Cache dashboard data in Redis
        cache_key = f"dashboard:{user.email}"
        cached_data = {
            "activity_status": {
                "is_active": bool(user.session_id),
                "last_active": user.session_updated_at.strftime("%b %d, %Y %H:%M:%S") if user.session_updated_at else None
            },
            "portfolio_overview": {
                "value": round(portfolio_value, 2),
                "change_percentage": round(portfolio_change, 2)
            },
            "ongoing_trades": [
                {
                    "stock": trade.stock_ticker,
                    "bought": trade.buy_price,
                    "quantity": trade.quantity,
                    "capital_used": trade.capital_used,
                    "profit": (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                              if trade.sell_price else 0
                } for trade in ongoing_trades
            ],
            "recent_trades": [
                {
                    "date": trade.order_executed_at.strftime("%b %d, %Y %H:%M:%S"),
                    "stock": trade.stock_ticker,
                    "bought": trade.buy_price,
                    "sold": trade.sell_price or 0,
                    "quantity": trade.quantity,
                    "capital_used": trade.capital_used,
                    "profit": (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                              if trade.sell_price else 0
                } for trade in recent_trades
            ],
            "overall_profit": {
                "value": round(total_profit, 2),
                "percentage": round(portfolio_change, 2),
                "last_7_days": [
                    sum(
                        (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                        for trade in db.query(Trade).filter(
                            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=7-i),
                            Trade.order_executed_at < datetime.utcnow() - timedelta(days=6-i),
                            Trade.sell_price.isnot(None)
                        ).all()
                    )
                    for i in range(7)
                ]
            },
            "unused_funds": unused_funds,
            "allocated_funds": allocated_funds,
            "upcoming_trades": {
                "count": len(upcoming_trades),
                "holding_period": "3 Days"  # Placeholder; calculate based on order data
            }
        }
        await redis_client.setex(cache_key, 300, json.dumps(cached_data))
        log_action("dashboard_data_fetched", current_user, correlation_id, {"cached": True})

        return cached_data
    except Exception as e:
        log_error("fetch_dashboard_data_failed", e, current_user, correlation_id)
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")

# Brokerage Activation Endpoint
@router.post(
    "/activate-brokerage",
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def activate_brokerage(
    activation: BrokerageActivation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Activate a brokerage account (Zerodha or Groww) and store encrypted credentials.
    """
    correlation_id = await log_request(request, "activate_brokerage", current_user, {"brokerage": activation.brokerage})
    try:
        # Fetch user
        user = await get_user_by_email(db, current_user.email)
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        # Encrypt sensitive data
        encrypted_api_key = fernet.encrypt(activation.api_key.encode()).decode()
        encrypted_api_secret = fernet.encrypt(activation.api_secret.encode()).decode()
        encrypted_session_id = None
        encrypted_refresh_token = None

        # Brokerage-specific logic
        if activation.brokerage == "zerodha":
            if not activation.request_token:
                log_error("missing_request_token", Exception("Request token required"), user, correlation_id, {"broker": "zerodha"})
                raise HTTPException(status_code=400, detail="Request token required for Zerodha")

            async with httpx.AsyncClient() as client:
                try:
                    # Generate session using Kite Connect API
                    response = await client.post(
                        "https://api.kite.trade/session/token",
                        data={
                            "api_key": activation.api_key,
                            "request_token": activation.request_token,
                            "checksum": generate_zerodha_checksum(activation.api_key, activation.request_token, activation.api_secret)
                        },
                        timeout=10
                    )
                    if response.status_code != 200:
                        log_error("zerodha_session_creation_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                        raise HTTPException(status_code=400, detail="Failed to validate Zerodha credentials")
                    session_data = response.json()
                    access_token = session_data.get("data", {}).get("access_token")
                    refresh_token = session_data.get("data", {}).get("refresh_token")
                    if not access_token or not refresh_token:
                        log_error("invalid_zerodha_response", Exception("Missing access_token or refresh_token"), user, correlation_id, {"broker": "zerodha"})
                        raise HTTPException(status_code=400, detail="Invalid response from Zerodha")

                    # Encrypt tokens
                    encrypted_session_id = fernet.encrypt(access_token.encode()).decode()
                    encrypted_refresh_token = fernet.encrypt(refresh_token.encode()).decode()
                except httpx.RequestError as e:
                    log_error("zerodha_api_error", e, user, correlation_id, {"broker": "zerodha"})
                    raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

        elif activation.brokerage == "groww":
            # Placeholder: Assume Groww API
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        activation.api_url,
                        json={"api_key": activation.api_key, "api_secret": activation.api_secret},
                        timeout=10
                    )
                    if response.status_code != 200:
                        log_error("groww_session_creation_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "groww", "status_code": response.status_code})
                        raise HTTPException(status_code=400, detail="Failed to validate Groww credentials")
                    session_data = response.json()
                    session_id = session_data.get("session_id", "mock-groww-session-id")
                    encrypted_session_id = fernet.encrypt(session_id.encode()).decode()
                except httpx.RequestError as e:
                    log_error("groww_api_error", e, user, correlation_id, {"broker": "groww"})
                    raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

        # Update user with encrypted brokerage details
        user.broker = activation.brokerage
        user.api_key = encrypted_api_key
        user.api_secret = encrypted_api_secret
        user.session_id = encrypted_session_id
        user.broker_refresh_token = encrypted_refresh_token
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        log_action("brokerage_activated", user, correlation_id, {"broker": activation.brokerage})
        return {"message": f"{activation.brokerage} activated successfully", "session_id": fernet.decrypt(encrypted_session_id.encode()).decode()}
    except Exception as e:
        log_error("brokerage_activation_failed", e, current_user, correlation_id, {"broker": activation.brokerage})
        raise HTTPException(status_code=500, detail=f"Error activating brokerage: {str(e)}")

# View Specific Trade Endpoint
@router.get(
    "/trade/{trade_id}",
    response_model=TradeOut,
    dependencies=[Depends(RateLimiter(times=5, seconds=1))]
)
async def get_trade(trade_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), request: Request = None):
    """
    Fetch details of a specific trade by ID.
    """
    correlation_id = await log_request(request, "view_trade", current_user, {"trade_id": trade_id})
    try:
        trade = db.query(Trade).options(selectinload(Trade.order)).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
        if not trade:
            log_error("trade_not_found", Exception("Trade not found"), current_user, correlation_id, {"trade_id": trade_id})
            raise HTTPException(status_code=404, detail="Trade not found")
        log_action("trade_viewed", current_user, correlation_id, {"trade_id": trade_id, "stock_ticker": trade.stock_ticker})
        return trade
    except Exception as e:
        log_error("view_trade_failed", e, current_user, correlation_id, {"trade_id": trade_id})
        raise HTTPException(status_code=500, detail=f"Error fetching trade: {str(e)}")

# Place Buy Order Endpoint
@router.post(
    "/order/buy",
    response_model=OrderOut,
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def place_buy_order(
    order: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Place a buy order with the specified brokerage.
    """
    correlation_id = await log_request(request, "place_buy_order", current_user, {"stock_ticker": order.stock_ticker, "quantity": order.quantity})
    try:
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if user.broker != "zerodha" or not user.session_id:
            log_error("broker_not_activated", Exception("Broker not activated"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Broker not activated")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.kite.trade/orders/regular",
                    headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                    data={
                        "tradingsymbol": order.stock_ticker,
                        "exchange": "NSE",
                        "transaction_type": "BUY",
                        "order_type": "MARKET",
                        "quantity": order.quantity,
                        "product": "CNC"
                    },
                    timeout=10
                )
                if response.status_code == 401:
                    log_action("attempt_zerodha_session_refresh", user, correlation_id, {"broker": "zerodha"})
                    new_access_token = await refresh_zerodha_session(user, db, request, correlation_id)
                    response = await client.post(
                        "https://api.kite.trade/orders/regular",
                        headers={"Authorization": f"token {new_access_token}"},
                        data={
                            "tradingsymbol": order.stock_ticker,
                            "exchange": "NSE",
                            "transaction_type": "BUY",
                            "order_type": "MARKET",
                            "quantity": order.quantity,
                            "product": "CNC"
                        },
                        timeout=10
                    )
                if response.status_code != 200:
                    log_error("zerodha_order_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                    raise HTTPException(status_code=400, detail="Failed to place buy order")
                
                order_data = response.json().get("data", {})
                new_order = Order(
                    user_id=user.id,
                    stock_ticker=order.stock_ticker,
                    quantity=order.quantity,
                    order_type="buy",
                    price=order.price,
                    status="executed",
                    order_executed_at=datetime.utcnow()
                )
                db.add(new_order)
                db.commit()
                db.refresh(new_order)
                log_action("buy_order_placed", user, correlation_id, {"stock_ticker": order.stock_ticker, "quantity": order.quantity, "order_id": new_order.id})
                return new_order
            except httpx.RequestError as e:
                log_error("zerodha_order_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")
    except Exception as e:
        log_error("place_buy_order_failed", e, current_user, correlation_id, {"stock_ticker": order.stock_ticker})
        raise HTTPException(status_code=500, detail=f"Error placing buy order: {str(e)}")

# Place Sell Order Endpoint
@router.post(
    "/order/sell",
    response_model=OrderOut,
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def place_sell_order(
    order: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Place a sell order with the specified brokerage.
    """
    correlation_id = await log_request(request, "place_sell_order", current_user, {"stock_ticker": order.stock_ticker, "quantity": order.quantity})
    try:
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if user.broker != "zerodha" or not user.session_id:
            log_error("broker_not_activated", Exception("Broker not activated"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Broker not activated")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.kite.trade/orders/regular",
                    headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                    data={
                        "tradingsymbol": order.stock_ticker,
                        "exchange": "NSE",
                        "transaction_type": "SELL",
                        "order_type": "MARKET",
                        "quantity": order.quantity,
                        "product": "CNC"
                    },
                    timeout=10
                )
                if response.status_code == 401:
                    log_action("attempt_zerodha_session_refresh", user, correlation_id, {"broker": "zerodha"})
                    new_access_token = await refresh_zerodha_session(user, db, request, correlation_id)
                    response = await client.post(
                        "https://api.kite.trade/orders/regular",
                        headers={"Authorization": f"token {new_access_token}"},
                        data={
                            "tradingsymbol": order.stock_ticker,
                            "exchange": "NSE",
                            "transaction_type": "SELL",
                            "order_type": "MARKET",
                            "quantity": order.quantity,
                            "product": "CNC"
                        },
                        timeout=10
                    )
                if response.status_code != 200:
                    log_error("zerodha_order_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                    raise HTTPException(status_code=400, detail="Failed to place sell order")
                
                order_data = response.json().get("data", {})
                new_order = Order(
                    user_id=user.id,
                    stock_ticker=order.stock_ticker,
                    quantity=order.quantity,
                    order_type="sell",
                    price=order.price,
                    status="executed",
                    order_executed_at=datetime.utcnow()
                )
                db.add(new_order)
                db.commit()
                db.refresh(new_order)
                log_action("sell_order_placed", user, correlation_id, {"stock_ticker": order.stock_ticker, "quantity": order.quantity, "order_id": new_order.id})
                return new_order
            except httpx.RequestError as e:
                log_error("zerodha_order_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")
    except Exception as e:
        log_error("place_sell_order_failed", e, current_user, correlation_id, {"stock_ticker": order.stock_ticker})
        raise HTTPException(status_code=500, detail=f"Error placing sell order: {str(e)}")

def generate_zerodha_checksum(api_key: str, token: str, api_secret: str) -> str:
    """
    Generate checksum for Zerodha Kite Connect API session request or refresh.
    """
    from hashlib import sha256
    return sha256(f"{api_key}{token}{api_secret}".encode()).hexdigest()
