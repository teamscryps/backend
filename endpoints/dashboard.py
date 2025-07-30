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
from growwapi import GrowwAPI
import pyotp
import upstox_client
from upstox_client.rest import ApiException

# Initialize Fernet for encryption
fernet = Fernet(settings.ENCRYPTION_KEY)

# Initialize Redis for rate limiting and caching
try:
    redis_client = redis.from_url(settings.REDIS_URL)
    # Initialize rate limiter
    async def init_rate_limiter():
        try:
            await FastAPILimiter.init(redis_client)
        except Exception as e:
            print(f"Failed to initialize rate limiter: {e}")
            # Continue without rate limiting
    router = APIRouter(dependencies=[Depends(init_rate_limiter)])
except Exception as e:
    print(f"Redis not available: {e}")
    # Fallback without rate limiting
    router = APIRouter()

# Pydantic schemas
class BrokerageActivation(BaseModel):
    brokerage: str
    api_url: HttpUrl
    api_key: str
    api_secret: str
    request_token: str | None = None  # For Zerodha
    totp_secret: str | None = None  # For Groww
    auth_code: str | None = None  # For Upstox OAuth

    @validator("brokerage")
    def validate_brokerage(cls, v):
        valid_brokerages = ["zerodha", "groww", "upstox"]
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
    Returns the new access_token (session_id).
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

async def get_groww_access_token(user: UserModel, db: Session, correlation_id: str) -> str:
    """
    Retrieve or refresh Groww access token.
    """
    log_action("get_groww_access_token_start", user, correlation_id, {"broker": "groww"})
    # Decrypt stored values
    dec_api_key = fernet.decrypt(user.api_key.encode()).decode()
    dec_secret = fernet.decrypt(user.api_secret.encode()).decode()
    dec_totp_secret = fernet.decrypt(user.broker_refresh_token.encode()).decode() if user.broker_refresh_token else None

    if user.session_id:
        # Reuse existing token
        token = fernet.decrypt(user.session_id.encode()).decode()
        log_action("groww_session_reused", user, correlation_id, {"broker": "groww"})
        return token

    # Generate via TOTP using SDK
    try:
        if not dec_totp_secret:
            log_error("missing_totp_secret", Exception("No TOTP secret available"), user, correlation_id, {"broker": "groww"})
            raise HTTPException(status_code=400, detail="No TOTP secret available")
        totp = pyotp.TOTP(dec_totp_secret).now()
        access_token = GrowwAPI.get_access_token(dec_api_key, totp)
        # Save encrypted session ID
        user.session_id = fernet.encrypt(access_token.encode()).decode()
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        log_action("groww_session_created", user, correlation_id, {"broker": "groww"})
        return access_token
    except Exception as e:
        log_error("groww_totp_token_failed", e, user, correlation_id, {"broker": "groww"})
        raise HTTPException(status_code=400, detail=f"Failed to obtain Groww access token: {str(e)}")

async def get_upstox_access_token(user: UserModel, db: Session, correlation_id: str, auth_code: str = None) -> str:
    """
    Retrieve or refresh Upstox access token.
    """
    log_action("get_upstox_access_token_start", user, correlation_id, {"broker": "upstox"})
    if user.session_id and not auth_code:
        # Reuse existing token
        token = fernet.decrypt(user.session_id.encode()).decode()
        log_action("upstox_session_reused", user, correlation_id, {"broker": "upstox"})
        return token

    # Generate new token using auth_code
    try:
        if not auth_code:
            log_error("missing_auth_code", Exception("Authorization code required"), user, correlation_id, {"broker": "upstox"})
            raise HTTPException(status_code=400, detail="Authorization code required for Upstox")
        session = upstox_client.Configuration()
        session.client_id = settings.UPSTOX_API_KEY
        session.client_secret = settings.UPSTOX_API_SECRET
        session.redirect_uri = settings.UPSTOX_REDIRECT_URL
        access_token = session.retrieve_access_token(auth_code)
        # Save encrypted session ID
        user.session_id = fernet.encrypt(access_token.encode()).decode()
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        log_action("upstox_session_created", user, correlation_id, {"broker": "upstox"})
        return access_token
    except ApiException as e:
        log_error("upstox_token_failed", e, user, correlation_id, {"broker": "upstox"})
        raise HTTPException(status_code=400, detail=f"Failed to obtain Upstox access token: {str(e)}")

# Dashboard Data Endpoint
@router.get(
    "/dashboard",
    response_model=dict
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

        unused_funds = 2300  # Placeholder for non-brokerage case
        allocated_funds = 0
        holdings = []

        # Validate brokerage session
        if user.broker == "zerodha" and user.session_id:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        "https://api.kite.trade/portfolio/holdings",
                        headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                        timeout=5
                    )
                    if response.status_code == 401:
                        log_action("attempt_zerodha_session_refresh", user, correlation_id, {"broker": "zerodha"})
                        new_access_token = await refresh_zerodha_session(user, db, request, correlation_id)
                        response = await client.get(
                            "https://api.kite.trade/portfolio/holdings",
                            headers={"Authorization": f"token {new_access_token}"},
                            timeout=5
                        )
                        if response.status_code != 200:
                            log_error("zerodha_holdings_fetch_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                            raise HTTPException(status_code=401, detail="Failed to validate Zerodha session")
                    if response.status_code == 200:
                        holdings = response.json().get("data", [])
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
                    log_error("zerodha_api_error", e, user, correlation_id, {"broker": "zerodha"})
                    raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

        elif user.broker == "groww" and user.session_id:
            access_token = await get_groww_access_token(user, db, correlation_id)
            groww = GrowwAPI(access_token)
            try:
                margins = groww.get_margin_for_user(timeout=5)
                unused_funds = margins.get("cash_available", 0)
                allocated_funds = margins.get("utilised_debit", 0)
                holdings = groww.get_holdings_for_user(timeout=5)
                log_action("groww_portfolio_fetched", user, correlation_id, {"broker": "groww"})
            except Exception as e:
                log_error("groww_portfolio_fetch_failed", e, user, correlation_id, {"broker": "groww"})
                raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

        elif user.broker == "upstox" and user.session_id:
            try:
                dec_token = fernet.decrypt(user.session_id.encode()).decode()
                config = upstox_client.Configuration()
                config.access_token = dec_token
                config.api_key = settings.UPSTOX_API_KEY
                api = upstox_client.PortfolioApi(upstox_client.ApiClient(config))
                margins = api.get_margins()
                holdings = api.get_holdings()
                unused_funds = margins.cash if hasattr(margins, 'cash') else 0
                allocated_funds = margins.used_margin if hasattr(margins, 'used_margin') else 0
                log_action("upstox_portfolio_fetched", user, correlation_id, {"broker": "upstox"})
            except ApiException as e:
                if e.status == 401:
                    log_error("upstox_session_invalid", e, user, correlation_id, {"broker": "upstox", "status_code": e.status})
                    raise HTTPException(status_code=401, detail="Upstox session invalid; please re-authenticate")
                log_error("upstox_portfolio_fetch_failed", e, user, correlation_id, {"broker": "upstox"})
                raise HTTPException(status_code=503, detail=f"Upstox service unavailable: {str(e)}")

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

        # Calculate portfolio overview
        total_invested = sum(trade.capital_used for trade in ongoing_trades)
        total_profit = sum(
            (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
            for trade in recent_trades if trade.sell_price
        )
        portfolio_value = total_invested + total_profit
        portfolio_change = (total_profit / total_invested * 100) if total_invested > 0 else 0

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
        
        # Cache dashboard data in Redis (if available)
        try:
            cache_key = f"dashboard:{user.email}"
            await redis_client.setex(cache_key, 300, json.dumps(cached_data))
            log_action("dashboard_data_fetched", current_user, correlation_id, {"broker": user.broker, "cached": True})
        except Exception as e:
            print(f"Redis caching failed: {e}")
            log_action("dashboard_data_fetched", current_user, correlation_id, {"broker": user.broker, "cached": False})
        
        return cached_data
    except Exception as e:
        log_error("fetch_dashboard_data_failed", e, current_user, correlation_id, {"broker": user.broker})
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")

# Brokerage Activation Endpoint
@router.post(
    "/activate-brokerage"
)
async def activate_brokerage(
    activation: BrokerageActivation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Activate a brokerage account (Zerodha, Groww, or Upstox) and store encrypted credentials.
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
            if not activation.totp_secret:
                log_error("missing_totp_secret", Exception("TOTP secret required"), user, correlation_id, {"broker": "groww"})
                raise HTTPException(status_code=400, detail="TOTP secret required for Groww")
            try:
                totp = pyotp.TOTP(activation.totp_secret).now()
                access_token = GrowwAPI.get_access_token(activation.api_key, totp)
                encrypted_session_id = fernet.encrypt(access_token.encode()).decode()
                encrypted_refresh_token = fernet.encrypt(activation.totp_secret.encode()).decode()  # Store TOTP secret as refresh_token
                log_action("groww_session_created", user, correlation_id, {"broker": "groww"})
            except Exception as e:
                log_error("groww_session_creation_failed", e, user, correlation_id, {"broker": "groww"})
                raise HTTPException(status_code=400, detail=f"Failed to validate Groww credentials: {str(e)}")

        elif activation.brokerage == "upstox":
            if not activation.auth_code:
                log_error("missing_auth_code", Exception("Authorization code required"), user, correlation_id, {"broker": "upstox"})
                raise HTTPException(status_code=400, detail="Authorization code required for Upstox")
            try:
                session = upstox_client.Configuration()
                session.client_id = activation.api_key
                session.client_secret = activation.api_secret
                session.redirect_uri = activation.api_url
                access_token = session.retrieve_access_token(activation.auth_code)
                encrypted_session_id = fernet.encrypt(access_token.encode()).decode()
                # Upstox refresh token not stored; requires re-authentication
                log_action("upstox_session_created", user, correlation_id, {"broker": "upstox"})
            except ApiException as e:
                log_error("upstox_session_creation_failed", e, user, correlation_id, {"broker": "upstox"})
                raise HTTPException(status_code=400, detail=f"Failed to validate Upstox credentials: {str(e)}")

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
    response_model=TradeOut
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
    response_model=OrderOut
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

        if not user.session_id:
            log_error("broker_not_activated", Exception("Broker not activated"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Broker not activated")

        if user.broker == "zerodha":
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
                except httpx.RequestError as e:
                    log_error("zerodha_order_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

        elif user.broker == "groww":
            access_token = await get_groww_access_token(user, db, correlation_id)
            groww = GrowwAPI(access_token)
            try:
                response = groww.place_order(
                    symbol=order.stock_ticker,
                    exchange="NSE",
                    transaction_type="BUY",
                    order_type="MARKET",
                    quantity=order.quantity,
                    product="DELIVERY",
                    timeout=10
                )
                if not response.get("success"):
                    log_error("groww_order_failed", Exception("Order placement failed"), user, correlation_id, {"broker": "groww", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Groww buy order")
            except Exception as e:
                log_error("groww_order_api_error", e, user, correlation_id, {"broker": "groww", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

        elif user.broker == "upstox":
            try:
                dec_token = fernet.decrypt(user.session_id.encode()).decode()
                config = upstox_client.Configuration()
                config.access_token = dec_token
                config.api_key = settings.UPSTOX_API_KEY
                api = upstox_client.OrderApi(upstox_client.ApiClient(config))
                response = api.place_order(
                    quantity=order.quantity,
                    product="D",  # Delivery
                    validity="DAY",
                    price=0,  # Market order
                    tag="",
                    instrument_token=order.stock_ticker,
                    order_type="MARKET",
                    transaction_type="BUY",
                    disclosed_quantity=0,
                    trigger_price=0,
                    is_amo=False
                )
                if not response or not hasattr(response, 'order_id'):
                    log_error("upstox_order_failed", Exception("Order placement failed"), user, correlation_id, {"broker": "upstox", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Upstox buy order")
            except ApiException as e:
                if e.status == 401:
                    log_error("upstox_session_invalid", e, user, correlation_id, {"broker": "upstox", "status_code": e.status})
                    raise HTTPException(status_code=401, detail="Upstox session invalid; please re-authenticate")
                log_error("upstox_order_api_error", e, user, correlation_id, {"broker": "upstox", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Upstox service unavailable: {str(e)}")

        order_data = response.get("data", {}) if user.broker in ["zerodha", "groww"] else response
        new_order = Order(
            user_id=user.id,
            stock_symbol=order.stock_ticker,
            quantity=order.quantity,
            order_type="buy",
            price=order.price,
            order_executed_at=datetime.utcnow()
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        log_action("buy_order_placed", user, correlation_id, {"stock_ticker": order.stock_ticker, "quantity": order.quantity, "order_id": new_order.id, "broker": user.broker})
        return new_order
    except Exception as e:
        log_error("place_buy_order_failed", e, current_user, correlation_id, {"stock_ticker": order.stock_ticker, "broker": user.broker})
        raise HTTPException(status_code=500, detail=f"Error placing buy order: {str(e)}")

# Place Sell Order Endpoint
@router.post(
    "/order/sell",
    response_model=OrderOut
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

        if not user.session_id:
            log_error("broker_not_activated", Exception("Broker not activated"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Broker not activated")

        if user.broker == "zerodha":
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
                except httpx.RequestError as e:
                    log_error("zerodha_order_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

        elif user.broker == "groww":
            access_token = await get_groww_access_token(user, db, correlation_id)
            groww = GrowwAPI(access_token)
            try:
                response = groww.place_order(
                    symbol=order.stock_ticker,
                    exchange="NSE",
                    transaction_type="SELL",
                    order_type="MARKET",
                    quantity=order.quantity,
                    product="DELIVERY",
                    timeout=10
                )
                if not response.get("success"):
                    log_error("groww_order_failed", Exception("Order placement failed"), user, correlation_id, {"broker": "groww", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Groww sell order")
            except Exception as e:
                log_error("groww_order_api_error", e, user, correlation_id, {"broker": "groww", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

        elif user.broker == "upstox":
            try:
                dec_token = fernet.decrypt(user.session_id.encode()).decode()
                config = upstox_client.Configuration()
                config.access_token = dec_token
                config.api_key = settings.UPSTOX_API_KEY
                api = upstox_client.OrderApi(upstox_client.ApiClient(config))
                response = api.place_order(
                    quantity=order.quantity,
                    product="D",  # Delivery
                    validity="DAY",
                    price=0,  # Market order
                    tag="",
                    instrument_token=order.stock_ticker,
                    order_type="MARKET",
                    transaction_type="SELL",
                    disclosed_quantity=0,
                    trigger_price=0,
                    is_amo=False
                )
                if not response or not hasattr(response, 'order_id'):
                    log_error("upstox_order_failed", Exception("Order placement failed"), user, correlation_id, {"broker": "upstox", "stock_ticker": order.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Upstox sell order")
            except ApiException as e:
                if e.status == 401:
                    log_error("upstox_session_invalid", e, user, correlation_id, {"broker": "upstox", "status_code": e.status})
                    raise HTTPException(status_code=401, detail="Upstox session invalid; please re-authenticate")
                log_error("upstox_order_api_error", e, user, correlation_id, {"broker": "upstox", "stock_ticker": order.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Upstox service unavailable: {str(e)}")

        order_data = response.get("data", {}) if user.broker in ["zerodha", "groww"] else response
        new_order = Order(
            user_id=user.id,
            stock_symbol=order.stock_ticker,
            quantity=order.quantity,
            order_type="sell",
            price=order.price,
            order_executed_at=datetime.utcnow()
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        log_action("sell_order_placed", user, correlation_id, {"stock_ticker": order.stock_ticker, "quantity": order.quantity, "order_id": new_order.id, "broker": user.broker})
        return new_order
    except Exception as e:
        log_error("place_sell_order_failed", e, current_user, correlation_id, {"stock_ticker": order.stock_ticker, "broker": user.broker})
        raise HTTPException(status_code=500, detail=f"Error placing sell order: {str(e)}")

def generate_zerodha_checksum(api_key: str, token: str, api_secret: str) -> str:
    """
    Generate checksum for Zerodha Kite Connect API session request or refresh.
    """
    from hashlib import sha256
    return sha256(f"{api_key}{token}{api_secret}".encode()).hexdigest()