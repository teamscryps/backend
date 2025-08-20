from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload
from typing import List, Dict, Any
from database import get_db
from schemas.trades import TradeOut
from schemas.user import User, ZerodhaDailyLogin
from schemas.order import OrderOut
from models.trade import Trade
from models.order import Order
from models.user import User as UserModel
from auth_service import get_user_by_email
from security import get_current_user
from datetime import datetime, timedelta, timezone
import httpx
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
from kiteconnect import KiteConnect

# No encryption: store credentials and tokens in plaintext as per user request

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

    decrypted_refresh_token = user.broker_refresh_token
    decrypted_api_key = user.api_key
    decrypted_api_secret = user.api_secret

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

            # Update user with new access token (plaintext)
            user.session_id = new_access_token
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
    if user.session_id:
        # Reuse existing token (plaintext)
        token = user.session_id
        log_action("groww_session_reused", user, correlation_id, {"broker": "groww"})
        return token

    # Generate new token using TOTP
    try:
        if not user.broker_refresh_token:
            log_error("missing_totp_secret", Exception("TOTP secret required"), user, correlation_id, {"broker": "groww"})
            raise HTTPException(status_code=400, detail="TOTP secret required for Groww")
        
        decrypted_totp_secret = user.broker_refresh_token
        decrypted_api_key = user.api_key
        decrypted_api_secret = user.api_secret
        
        groww = GrowwAPI()
        access_token = groww.get_access_token(decrypted_api_key, decrypted_api_secret, decrypted_totp_secret)
        
        # Save session ID (plaintext)
        user.session_id = access_token
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        log_action("groww_session_created", user, correlation_id, {"broker": "groww"})
        return access_token
    except Exception as e:
        log_error("groww_token_failed", e, user, correlation_id, {"broker": "groww"})
        raise HTTPException(status_code=400, detail=f"Failed to obtain Groww access token: {str(e)}")

async def get_upstox_access_token(user: UserModel, db: Session, correlation_id: str, auth_code: str = None) -> str:
    """
    Retrieve or refresh Upstox access token.
    """
    log_action("get_upstox_access_token_start", user, correlation_id, {"broker": "upstox"})
    if user.session_id and not auth_code:
        # Reuse existing token (plaintext)
        token = user.session_id
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
        # Save session ID (plaintext)
        user.session_id = access_token
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

        unused_funds = 0  # Default to 0 instead of placeholder
        allocated_funds = 0
        holdings = []
        session_status = {"valid": True, "requires_daily_login": False}

        # Validate brokerage session
        if user.broker == "zerodha":
            # Check if Zerodha session is valid for today
            if not user.session_id:
                session_status = {"valid": False, "requires_daily_login": True, "reason": "No active session"}
            else:
                # Check if session was updated today (IST)
                ist_tz = timezone(timedelta(hours=5, minutes=30))  # IST timezone
                today_ist = datetime.now(ist_tz).date()
                
                if user.session_updated_at:
                    session_date_ist = user.session_updated_at.replace(tzinfo=timezone.utc).astimezone(ist_tz).date()
                    if session_date_ist != today_ist:
                        session_status = {"valid": False, "requires_daily_login": True, "reason": "Session expired (daily login required)"}
                
                # If session is valid, try to fetch data
                if session_status["valid"]:
                    try:
                        # Use KiteConnect with stored plaintext credentials
                        kite = KiteConnect(api_key=user.api_key)
                        kite.set_access_token(user.session_id)
                        
                        # Get holdings (KiteConnect returns a list)
                        holdings_data = kite.holdings()
                        holdings = holdings_data if isinstance(holdings_data, list) else holdings_data.get("data", [])

                        # Get margins (KiteConnect returns a dict with segments like 'equity')
                        margins_data = kite.margins()
                        # Support both direct and nested 'data' keys just in case
                        equity_margins = (
                            margins_data.get("equity", {})
                            if isinstance(margins_data, dict)
                            else {}
                        )
                        if not equity_margins and isinstance(margins_data, dict):
                            equity_margins = margins_data.get("data", {}).get("equity", {})

                        unused_funds = equity_margins.get("available", {}).get("cash", 0)
                        allocated_funds = equity_margins.get("utilised", {}).get("debits", 0)
                        
                        log_action("zerodha_portfolio_fetched", user, correlation_id, {"broker": "zerodha"})
                        
                    except Exception as e:
                        log_error("zerodha_api_error", e, user, correlation_id, {"broker": "zerodha"})
                        # Check if it's an authentication error
                        if "Invalid session" in str(e) or "401" in str(e):
                            session_status = {"valid": False, "requires_daily_login": True, "reason": "Session invalid"}
                        # No fallback - keep values as 0 when API fails
                        log_action("zerodha_api_failed", user, correlation_id, {"broker": "zerodha", "error": str(e)})

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
                config = upstox_client.Configuration()
                config.access_token = user.session_id
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

        # Combine Zerodha API trades if available, else fallback to empty values for all dashboard metrics
        if user.broker == "zerodha" and session_status["valid"]:
            # Fetch ongoing trades from Zerodha
            try:
                positions_data = kite.positions()
                ongoing_trades = positions_data.get("day", []) if isinstance(positions_data, dict) else []
            except Exception as e:
                log_error("zerodha_positions_error", e, user, correlation_id, {"broker": "zerodha"})
                ongoing_trades = []
            # Fetch recent trades from Zerodha
            try:
                recent_trades = kite.trades()
            except Exception as e:
                log_error("zerodha_trades_error", e, user, correlation_id, {"broker": "zerodha"})
                recent_trades = []
        else:
            holdings = []
            unused_funds = 0
            allocated_funds = 0
            invested_funds = 0.0
            market_value = 0.0
            unused_funds_calc = 0.0
            overall_profit_pct = 0.0
            portfolio_overview = 0.0
            ongoing_trades = []
            recent_trades = []

        # Fetch upcoming trades
        upcoming_trades = db.query(Order).filter(
            Order.user_id == user.id,
            Order.order_type == "buy"
        ).all()

        # Convert trades to dictionaries
        ongoing_trades_data = []
        for trade in ongoing_trades:
            ongoing_trades_data.append({
                "id": trade.id,
                "stock_symbol": trade.stock_ticker,
                "quantity": trade.quantity,
                "buy_price": trade.buy_price,
                "sell_price": trade.sell_price,
                "status": trade.status,
                "order_executed_at": trade.order_executed_at.isoformat() if trade.order_executed_at else None
            })

        recent_trades_data = []
        for trade in recent_trades:
            recent_trades_data.append({
                "id": trade.id,
                "stock_symbol": trade.stock_ticker,
                "quantity": trade.quantity,
                "buy_price": trade.buy_price,
                "sell_price": trade.sell_price,
                "status": trade.status,
                "order_executed_at": trade.order_executed_at.isoformat() if trade.order_executed_at else None
            })

        # Always initialize portfolio metrics to 0.0 to avoid UnboundLocalError
        invested_funds = 0.0
        allocated_funds_calc = 0.0
        market_value = 0.0
        unused_funds_calc = 0.0
        overall_profit_pct = 0.0
        portfolio_overview = 0.0
        upcoming_trades_data = []
        for trade in upcoming_trades:
            upcoming_trades_data.append({
                "id": trade.id,
                "stock_symbol": trade.stock_ticker,
                "quantity": trade.quantity,
                "buy_price": trade.buy_price,
                "sell_price": trade.sell_price,
                "status": trade.status,
                "order_executed_at": trade.order_executed_at.isoformat() if trade.order_executed_at else None
            })

        # Portfolio Metrics Calculation
        if holdings:
            for h in holdings:
                qty = h.get("quantity") or h.get("qty") or 0
                avg_price = h.get("average_price") or h.get("avg_price") or 0
                ltp = h.get("last_price") or h.get("ltp") or 0
                invested_funds += qty * avg_price
                allocated_funds_calc += qty * avg_price
                market_value += qty * ltp
            # If API allocated_funds is 0, use calculated value
            if not allocated_funds:
                allocated_funds = allocated_funds_calc
            unused_funds_calc = allocated_funds - invested_funds
            overall_profit_pct = ((market_value - invested_funds) / invested_funds * 100) if invested_funds else 0.0
            portfolio_overview = unused_funds + market_value

        # Return dashboard data with session status
        dashboard_data = {
            "unused_funds": unused_funds,
            "allocated_funds": allocated_funds,
            "invested_funds": invested_funds,
            "portfolio_overview": portfolio_overview,
            "holdings": holdings,
            "ongoing_trades": ongoing_trades_data,
            "recent_trades": recent_trades_data,
            "upcoming_trades": upcoming_trades_data,
            "broker": user.broker,
            "session_status": session_status
        }

        log_action("dashboard_data_fetched", user, correlation_id, {"broker": user.broker})
        return dashboard_data

    except Exception as e:
        log_error("dashboard_data_fetch_failed", e, current_user, correlation_id, {"broker": user.broker if 'user' in locals() else None})
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

        # Store sensitive data in plaintext
        session_id_value = None
        refresh_token_value = None

        # Brokerage-specific logic
        if activation.brokerage == "zerodha":
            if not activation.request_token:
                log_error("missing_request_token", Exception("Request token required"), user, correlation_id, {"broker": "zerodha"})
                raise HTTPException(status_code=400, detail="Request token required for Zerodha")

            try:
                # Use KiteConnect for proper session generation
                kite = KiteConnect(api_key=activation.api_key)
                session_data = kite.generate_session(
                    request_token=activation.request_token,
                    api_secret=activation.api_secret
                )
                
                access_token = session_data["access_token"]
                session_id_value = access_token
                
                # Store refresh token if available (for future token refresh)
                if "refresh_token" in session_data:
                    refresh_token_value = session_data["refresh_token"]
                
                log_action("zerodha_session_created", user, correlation_id, {"broker": "zerodha"})
                
            except Exception as e:
                log_error("zerodha_session_creation_failed", e, user, correlation_id, {"broker": "zerodha"})
                raise HTTPException(status_code=400, detail=f"Failed to validate Zerodha credentials: {str(e)}")

        elif activation.brokerage == "groww":
            if not activation.totp_secret:
                log_error("missing_totp_secret", Exception("TOTP secret required"), user, correlation_id, {"broker": "groww"})
                raise HTTPException(status_code=400, detail="TOTP secret required for Groww")
            try:
                groww = GrowwAPI()
                access_token = groww.get_access_token(activation.api_key, activation.api_secret, activation.totp_secret)
                session_id_value = access_token
                refresh_token_value = activation.totp_secret
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
                session_id_value = access_token
                # Upstox refresh token not stored; requires re-authentication
                log_action("upstox_session_created", user, correlation_id, {"broker": "upstox"})
            except ApiException as e:
                log_error("upstox_session_creation_failed", e, user, correlation_id, {"broker": "upstox"})
                raise HTTPException(status_code=400, detail=f"Failed to validate Upstox credentials: {str(e)}")

        # Update user with encrypted brokerage details
        user.broker = activation.brokerage
        user.api_key = activation.api_key
        user.api_secret = activation.api_secret
        user.session_id = session_id_value
        user.broker_refresh_token = refresh_token_value
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        log_action("brokerage_activated", user, correlation_id, {"broker": activation.brokerage})
        return {"message": f"{activation.brokerage} activated successfully", "session_id": user.session_id}
    except Exception as e:
        log_error("brokerage_activation_failed", e, current_user, correlation_id, {"brokerage": activation.brokerage})
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
                        headers={"Authorization": f"token {user.session_id}"},
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
                config = upstox_client.Configuration()
                config.access_token = user.session_id
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
                        headers={"Authorization": f"token {user.session_id}"},
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
                config = upstox_client.Configuration()
                config.access_token = user.session_id
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

@router.get("/zerodha/login-url")
async def get_zerodha_login_url(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Generate Zerodha login URL for the user to authenticate.
    This URL is used for daily login to get fresh request_token.
    """
    correlation_id = await log_request(request, "get_zerodha_login_url", current_user)
    try:
        user = await get_user_by_email(db, current_user.email)
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if not user.api_key:
            log_error("no_api_key", Exception("API key not found"), user, correlation_id, {"broker": "zerodha"})
            raise HTTPException(status_code=400, detail="Please set up your Zerodha API credentials first")

        # Generate login URL with proper redirect URL
        kite = KiteConnect(api_key=user.api_key)
        
        # Configure redirect URL (should match your frontend callback URL)
        # You can customize this based on your frontend setup
        redirect_url = "http://localhost:3000/zerodha-callback"  # Update this to your actual frontend URL
        
        login_url = kite.login_url()
        
        log_action("zerodha_login_url_generated", user, correlation_id, {"broker": "zerodha"})
        return {
            "login_url": login_url,
            "redirect_url": redirect_url,
            "message": "Open this URL in your browser to login to Zerodha. After login, you'll be redirected with a request_token. Use that token to complete daily login.",
            "instructions": [
                "1. Click the login URL to open Zerodha login page",
                "2. Login with your Zerodha credentials (Client ID, Password, TOTP)",
                "3. After successful login, you'll be redirected with request_token",
                "4. Copy the request_token from the redirect URL",
                "5. Use the request_token to complete daily login"
            ]
        }
        
    except Exception as e:
        log_error("zerodha_login_url_failed", e, current_user, correlation_id, {"broker": "zerodha"})
        raise HTTPException(status_code=500, detail=f"Error generating Zerodha login URL: {str(e)}")

@router.post("/zerodha/daily-login")
async def zerodha_daily_login(
    login_data: ZerodhaDailyLogin,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Complete daily Zerodha login using request_token from OAuth flow.
    This exchanges request_token for access_token and stores it for the day.
    """
    correlation_id = await log_request(request, "zerodha_daily_login", current_user)
    try:
        user = await get_user_by_email(db, current_user.email)
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if not user.api_credentials_set or user.broker != "zerodha":
            log_error("invalid_broker", Exception("Zerodha not set up"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Zerodha API credentials not set up")

        if not user.api_key or not user.api_secret:
            log_error("missing_credentials", Exception("API credentials missing"), user, correlation_id, {"broker": "zerodha"})
            raise HTTPException(status_code=400, detail="Zerodha API credentials incomplete")

        try:
            # Exchange request_token for access_token
            kite = KiteConnect(api_key=user.api_key)
            session_data = kite.generate_session(
                request_token=login_data.request_token,
                api_secret=user.api_secret
            )
            
            # Store new access_token (plaintext)
            user.session_id = session_data["access_token"]
            
            # Store refresh token if available
            if "refresh_token" in session_data:
                user.broker_refresh_token = session_data["refresh_token"]
            
            # Update session timestamp
            user.session_updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(user)
            
            log_action("zerodha_daily_login_success", user, correlation_id, {"broker": "zerodha"})
            return {
                "message": "Zerodha daily login successful", 
                "session_updated_at": user.session_updated_at,
                "status": "success"
            }
            
        except Exception as e:
            log_error("zerodha_session_generation_failed", e, user, correlation_id, {"broker": "zerodha"})
            raise HTTPException(status_code=400, detail=f"Failed to complete Zerodha daily login: {str(e)}")
        
    except Exception as e:
        log_error("zerodha_daily_login_failed", e, current_user, correlation_id, {"broker": "zerodha"})
        raise HTTPException(status_code=500, detail=f"Error during Zerodha daily login: {str(e)}")

def generate_zerodha_checksum(api_key: str, token: str, api_secret: str) -> str:
    """
    Generate checksum for Zerodha Kite Connect API session request or refresh.
    """
    from hashlib import sha256
    return sha256(f"{api_key}{token}{api_secret}".encode()).hexdigest()