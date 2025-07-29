from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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
import logging
from sqlalchemy.orm import selectinload
import json

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Fernet for encryption
fernet = Fernet(settings.ENCRYPTION_KEY)

# Initialize Redis for rate limiting and caching
redis_client = redis.from_url(settings.REDIS_URL)

# Initialize rate limiter
async def init_rate_limiter():
    await FastAPILimiter.init(redis_client)

router = APIRouter(dependencies=[Depends(init_rate_limiter)])

# Pydantic schema for brokerage activation
class BrokerageActivation(BaseModel):
    brokerage: str
    api_url: HttpUrl
    api_key: str
    api_secret: str
    request_token: str | None = None

    @validator("brokerage")
    def validate_brokerage(cls, v):
        valid_brokerages = ["zerodha", "groww"]
        if v.lower() not in valid_brokerages:
            raise ValueError("Invalid brokerage")
        return v.lower()

async def refresh_zerodha_session(user: UserModel, db: Session) -> str:
    """
    Refresh Zerodha session using the refresh_token.
    Returns the new access_token.
    """
    if not user.broker_refresh_token:
        logger.error(f"No refresh token available for user: {user.email}")
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
                logger.error(f"Zerodha session refresh failed: {response.status_code}")
                raise HTTPException(status_code=400, detail="Failed to refresh Zerodha session")
            session_data = response.json()
            new_access_token = session_data.get("data", {}).get("access_token")
            if not new_access_token:
                logger.error(f"No access token received from Zerodha refresh for user: {user.email}")
                raise HTTPException(status_code=400, detail="No access token received from Zerodha")

            # Update user with new encrypted access token
            user.session_id = fernet.encrypt(new_access_token.encode()).decode()
            user.session_updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            logger.info(f"Zerodha session refreshed for user: {user.email}")
            return new_access_token
        except httpx.RequestError as e:
            logger.error(f"Zerodha refresh API error: {str(e)}")
            raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

# Dashboard Data Endpoint
@router.get(
    "/dashboard",
    response_model=dict,
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def get_dashboard_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch all data required for the dashboard, including trades, portfolio, and funds.
    """
    try:
        # Fetch user with eager loading
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            logger.error(f"User not found: {current_user.email}")
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
                        logger.warning(f"Invalid Zerodha session for user: {user.email}, attempting refresh")
                        # Attempt to refresh session
                        new_access_token = await refresh_zerodha_session(user, db)
                        # Retry holdings request with new token
                        response = await client.get(
                            "https://api.kite.trade/portfolio/holdings",
                            headers={"Authorization": f"token {new_access_token}"},
                            timeout=5
                        )
                        if response.status_code != 200:
                            logger.error(f"Zerodha holdings fetch failed after refresh: {response.status_code}")
                            raise HTTPException(status_code=401, detail="Failed to validate Zerodha session")
                except httpx.RequestError as e:
                    logger.error(f"Zerodha API error: {str(e)}")
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
                        logger.warning(f"Failed to fetch Zerodha margins: {response.status_code}")
                except httpx.RequestError as e:
                    logger.error(f"Zerodha margins API error: {str(e)}")

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
                "last_active": user.session_updated_at.isoformat() if user.session_updated_at else None
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
                    "date": trade.order_executed_at.strftime("%b %d"),
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

        return cached_data
    except Exception as e:
        logger.error(f"Error fetching dashboard data for {current_user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")

# Brokerage Activation Endpoint
@router.post(
    "/activate-brokerage",
    dependencies=[Depends(RateLimiter(times=3, seconds=1))]
)
async def activate_brokerage(
    activation: BrokerageActivation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Activate a brokerage account (Zerodha or Groww) and store encrypted credentials.
    """
    try:
        # Fetch user
        user = await get_user_by_email(db, current_user.email)
        if not user:
            logger.error(f"User not found: {current_user.email}")
            raise HTTPException(status_code=404, detail="User not found")

        # Encrypt sensitive data
        encrypted_api_key = fernet.encrypt(activation.api_key.encode()).decode()
        encrypted_api_secret = fernet.encrypt(activation.api_secret.encode()).decode()
        encrypted_session_id = None
        encrypted_refresh_token = None

        # Brokerage-specific logic
        if activation.brokerage == "zerodha":
            if not activation.request_token:
                logger.warning(f"Missing request token for Zerodha activation: {user.email}")
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
                        logger.error(f"Zerodha session creation failed: {response.status_code}")
                        raise HTTPException(status_code=400, detail="Failed to validate Zerodha credentials")
                    session_data = response.json()
                    access_token = session_data.get("data", {}).get("access_token")
                    refresh_token = session_data.get("data", {}).get("refresh_token")
                    if not access_token or not refresh_token:
                        logger.error(f"Missing access_token or refresh_token from Zerodha for user: {user.email}")
                        raise HTTPException(status_code=400, detail="Invalid response from Zerodha")

                    # Encrypt tokens
                    encrypted_session_id = fernet.encrypt(access_token.encode()).decode()
                    encrypted_refresh_token = fernet.encrypt(refresh_token.encode()).decode()
                except httpx.RequestError as e:
                    logger.error(f"Zerodha API error: {str(e)}")
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
                        logger.error(f"Groww session creation failed: {response.status_code}")
                        raise HTTPException(status_code=400, detail="Failed to validate Groww credentials")
                    session_data = response.json()
                    session_id = session_data.get("session_id", "mock-groww-session-id")
                    encrypted_session_id = fernet.encrypt(session_id.encode()).decode()
                except httpx.RequestError as e:
                    logger.error(f"Groww API error: {str(e)}")
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

        logger.info(f"Brokerage {activation.brokerage} activated for user: {user.email}")
        return {"message": f"{activation.brokerage} activated successfully", "session_id": fernet.decrypt(encrypted_session_id.encode()).decode()}
    except Exception as e:
        logger.error(f"Error activating brokerage for {current_user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error activating brokerage: {str(e)}")

def generate_zerodha_checksum(api_key: str, token: str, api_secret: str) -> str:
    """
    Generate checksum for Zerodha Kite Connect API session request or refresh.
    """
    from hashlib import sha256
    return sha256(f"{api_key}{token}{api_secret}".encode()).hexdigest()