from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload
from typing import List
from database import get_db
from schemas.trades import TradeOut, TradeCreate
from schemas.user import User
from models.trade import Trade
from models.order import Order
from models.user import User as UserModel
from security import get_current_user
from datetime import datetime
import httpx
from cryptography.fernet import Fernet
from config import settings
from fastapi_limiter.depends import RateLimiter
from endpoints.logs import log_action, log_error, log_request
from growwapi import GrowwAPI
import pyotp
import upstox_client
from upstox_client.rest import ApiException

# Initialize Fernet for encryption
fernet = Fernet(settings.ENCRYPTION_KEY)

router = APIRouter()

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
    dec_api_key = fernet.decrypt(user.api_key.encode()).decode()
    dec_secret = fernet.decrypt(user.api_secret.encode()).decode()
    dec_totp_secret = fernet.decrypt(user.broker_refresh_token.encode()).decode() if user.broker_refresh_token else None

    if user.session_id:
        token = fernet.decrypt(user.session_id.encode()).decode()
        log_action("groww_session_reused", user, correlation_id, {"broker": "groww"})
        return token

    try:
        if not dec_totp_secret:
            log_error("missing_totp_secret", Exception("No TOTP secret available"), user, correlation_id, {"broker": "groww"})
            raise HTTPException(status_code=400, detail="No TOTP secret available")
        totp = pyotp.TOTP(dec_totp_secret).now()
        access_token = GrowwAPI.get_access_token(dec_api_key, totp)
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
        token = fernet.decrypt(user.session_id.encode()).decode()
        log_action("upstox_session_reused", user, correlation_id, {"broker": "upstox"})
        return token

    try:
        if not auth_code:
            log_error("missing_auth_code", Exception("Authorization code required"), user, correlation_id, {"broker": "upstox"})
            raise HTTPException(status_code=400, detail="Authorization code required for Upstox")
        session = upstox_client.Configuration()
        session.client_id = settings.UPSTOX_API_KEY
        session.client_secret = settings.UPSTOX_API_SECRET
        session.redirect_uri = settings.UPSTOX_REDIRECT_URL
        access_token = session.retrieve_access_token(auth_code)
        user.session_id = fernet.encrypt(access_token.encode()).decode()
        user.session_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        log_action("upstox_session_created", user, correlation_id, {"broker": "upstox"})
        return access_token
    except ApiException as e:
        log_error("upstox_token_failed", e, user, correlation_id, {"broker": "upstox"})
        raise HTTPException(status_code=400, detail=f"Failed to obtain Upstox access token: {str(e)}")

@router.post(
    "/trade",
    response_model=TradeOut
)
async def create_trade(
    trade: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Create a new trade (buy or sell) with the specified brokerage.
    """
    correlation_id = await log_request(request, "create_trade", current_user, {"stock_ticker": trade.stock_ticker, "quantity": trade.quantity, "type": trade.type})
    try:
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if not user.session_id:
            log_error("broker_not_activated", Exception("Broker not activated"), user, correlation_id, {"broker": user.broker})
            raise HTTPException(status_code=400, detail="Broker not activated")

        response = None
        if user.broker == "zerodha":
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        "https://api.kite.trade/orders/regular",
                        headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                        data={
                            "tradingsymbol": trade.stock_ticker,
                            "exchange": "NSE",
                            "transaction_type": trade.order_type.upper(),
                            "order_type": "MARKET",
                            "quantity": trade.quantity,
                            "product": "MTF" if trade.type == "mtf" else "CNC"
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
                                "tradingsymbol": trade.stock_ticker,
                                "exchange": "NSE",
                                "transaction_type": trade.order_type.upper(),
                                "order_type": "MARKET",
                                "quantity": trade.quantity,
                                "product": "MTF" if trade.type == "mtf" else "CNC"
                            },
                            timeout=10
                        )
                    if response.status_code != 200:
                        log_error("zerodha_trade_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                        raise HTTPException(status_code=400, detail="Failed to place Zerodha trade")
                except httpx.RequestError as e:
                    log_error("zerodha_trade_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": trade.stock_ticker})
                    raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

        elif user.broker == "groww":
            access_token = await get_groww_access_token(user, db, correlation_id)
            groww = GrowwAPI(access_token)
            try:
                response = groww.place_order(
                    symbol=trade.stock_ticker,
                    exchange="NSE",
                    transaction_type=trade.order_type.upper(),
                    order_type="MARKET",
                    quantity=trade.quantity,
                    product="MTF" if trade.type == "mtf" else "DELIVERY",
                    timeout=10
                )
                if not response.get("success"):
                    log_error("groww_trade_failed", Exception("Trade placement failed"), user, correlation_id, {"broker": "groww", "stock_ticker": trade.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Groww trade")
            except Exception as e:
                log_error("groww_trade_api_error", e, user, correlation_id, {"broker": "groww", "stock_ticker": trade.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

        elif user.broker == "upstox":
            try:
                dec_token = fernet.decrypt(user.session_id.encode()).decode()
                config = upstox_client.Configuration()
                config.access_token = dec_token
                config.api_key = settings.UPSTOX_API_KEY
                api = upstox_client.OrderApi(upstox_client.ApiClient(config))
                response = api.place_order(
                    quantity=trade.quantity,
                    product="M" if trade.type == "mtf" else "D",
                    validity="DAY",
                    price=0,  # Market order
                    tag="",
                    instrument_token=trade.stock_ticker,
                    order_type="MARKET",
                    transaction_type=trade.order_type.upper(),
                    disclosed_quantity=0,
                    trigger_price=0,
                    is_amo=False
                )
                if not response or not hasattr(response, 'order_id'):
                    log_error("upstox_trade_failed", Exception("Trade placement failed"), user, correlation_id, {"broker": "upstox", "stock_ticker": trade.stock_ticker})
                    raise HTTPException(status_code=400, detail="Failed to place Upstox trade")
            except ApiException as e:
                if e.status == 401:
                    log_error("upstox_session_invalid", e, user, correlation_id, {"broker": "upstox", "status_code": e.status})
                    raise HTTPException(status_code=401, detail="Upstox session invalid; please re-authenticate")
                log_error("upstox_trade_api_error", e, user, correlation_id, {"broker": "upstox", "stock_ticker": trade.stock_ticker})
                raise HTTPException(status_code=503, detail=f"Upstox service unavailable: {str(e)}")

        # Create trade record
        new_trade = Trade(
            user_id=user.id,
            stock_ticker=trade.stock_ticker,
            buy_price=trade.buy_price if trade.order_type == "buy" else None,
            quantity=trade.quantity,
            capital_used=trade.buy_price * trade.quantity if trade.order_type == "buy" else 0,
            order_executed_at=datetime.utcnow(),
            status="open" if trade.order_type == "buy" else "closed",
            sell_price=trade.buy_price if trade.order_type == "sell" else None,
            brokerage_charge=trade.brokerage_charge or 0,
            mtf_charge=trade.mtf_charge or 0 if trade.trade_type == "mtf" else 0,
            trade_type=trade.trade_type
        )
        db.add(new_trade)
        db.commit()
        db.refresh(new_trade)
        log_action("trade_created", user, correlation_id, {
            "stock_ticker": trade.stock_ticker,
            "quantity": trade.quantity,
            "trade_id": new_trade.id,
            "broker": user.broker,
            "type": trade.type
        })
        return new_trade
    except Exception as e:
        log_error("create_trade_failed", e, current_user, correlation_id, {"stock_ticker": trade.stock_ticker, "broker": user.broker})
        raise HTTPException(status_code=500, detail=f"Error creating trade: {str(e)}")

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

@router.put(
    "/trade/{trade_id}",
    response_model=TradeOut
)
async def update_trade(
    trade_id: int,
    trade_update: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Update a trade (e.g., sell price, status).
    """
    correlation_id = await log_request(request, "update_trade", current_user, {"trade_id": trade_id, "stock_ticker": trade_update.stock_ticker})
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
        if not trade:
            log_error("trade_not_found", Exception("Trade not found"), current_user, correlation_id, {"trade_id": trade_id})
            raise HTTPException(status_code=404, detail="Trade not found")

        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            log_error("user_not_found", Exception("User not found"), current_user, correlation_id, {"email": current_user.email})
            raise HTTPException(status_code=404, detail="User not found")

        if trade_update.order_type == "sell" and trade.status == "open":
            # Execute sell order if closing an open trade
            if user.broker == "zerodha":
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            "https://api.kite.trade/orders/regular",
                            headers={"Authorization": f"token {fernet.decrypt(user.session_id.encode()).decode()}"},
                            data={
                                "tradingsymbol": trade_update.stock_ticker,
                                "exchange": "NSE",
                                "transaction_type": "SELL",
                                "order_type": "MARKET",
                                "quantity": trade_update.quantity,
                                "product": "MTF" if trade_update.type == "mtf" else "CNC"
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
                                    "tradingsymbol": trade_update.stock_ticker,
                                    "exchange": "NSE",
                                    "transaction_type": "SELL",
                                    "order_type": "MARKET",
                                    "quantity": trade_update.quantity,
                                    "product": "MTF" if trade_update.type == "mtf" else "CNC"
                                },
                                timeout=10
                            )
                        if response.status_code != 200:
                            log_error("zerodha_trade_failed", Exception(f"Status: {response.status_code}"), user, correlation_id, {"broker": "zerodha", "status_code": response.status_code})
                            raise HTTPException(status_code=400, detail="Failed to place Zerodha sell trade")
                    except httpx.RequestError as e:
                        log_error("zerodha_trade_api_error", e, user, correlation_id, {"broker": "zerodha", "stock_ticker": trade_update.stock_ticker})
                        raise HTTPException(status_code=503, detail=f"Zerodha service unavailable: {str(e)}")

            elif user.broker == "groww":
                access_token = await get_groww_access_token(user, db, correlation_id)
                groww = GrowwAPI(access_token)
                try:
                    response = groww.place_order(
                        symbol=trade_update.stock_ticker,
                        exchange="NSE",
                        transaction_type="SELL",
                        order_type="MARKET",
                        quantity=trade_update.quantity,
                        product="MTF" if trade_update.type == "mtf" else "DELIVERY",
                        timeout=10
                    )
                    if not response.get("success"):
                        log_error("groww_trade_failed", Exception("Trade placement failed"), user, correlation_id, {"broker": "groww", "stock_ticker": trade_update.stock_ticker})
                        raise HTTPException(status_code=400, detail="Failed to place Groww sell trade")
                except Exception as e:
                    log_error("groww_trade_api_error", e, user, correlation_id, {"broker": "groww", "stock_ticker": trade_update.stock_ticker})
                    raise HTTPException(status_code=503, detail=f"Groww service unavailable: {str(e)}")

            elif user.broker == "upstox":
                try:
                    dec_token = fernet.decrypt(user.session_id.encode()).decode()
                    config = upstox_client.Configuration()
                    config.access_token = dec_token
                    config.api_key = settings.UPSTOX_API_KEY
                    api = upstox_client.OrderApi(upstox_client.ApiClient(config))
                    response = api.place_order(
                        quantity=trade_update.quantity,
                        product="M" if trade_update.type == "mtf" else "D",
                        validity="DAY",
                        price=0,  # Market order
                        tag="",
                        instrument_token=trade_update.stock_ticker,
                        order_type="MARKET",
                        transaction_type="SELL",
                        disclosed_quantity=0,
                        trigger_price=0,
                        is_amo=False
                    )
                    if not response or not hasattr(response, 'order_id'):
                        log_error("upstox_trade_failed", Exception("Trade placement failed"), user, correlation_id, {"broker": "upstox", "stock_ticker": trade_update.stock_ticker})
                        raise HTTPException(status_code=400, detail="Failed to place Upstox sell trade")
                except ApiException as e:
                    if e.status == 401:
                        log_error("upstox_session_invalid", e, user, correlation_id, {"broker": "upstox", "status_code": e.status})
                        raise HTTPException(status_code=401, detail="Upstox session invalid; please re-authenticate")
                    log_error("upstox_trade_api_error", e, user, correlation_id, {"broker": "upstox", "stock_ticker": trade_update.stock_ticker})
                    raise HTTPException(status_code=503, detail=f"Upstox service unavailable: {str(e)}")

            trade.sell_price = trade_update.buy_price  # Use input price as sell_price
            trade.status = "closed"
            trade.brokerage_charge = trade_update.brokerage_charge or trade.brokerage_charge or 0
            trade.mtf_charge = trade_update.mtf_charge or trade.mtf_charge or 0 if trade_update.type == "mtf" else 0
        else:
            # Update non-sell fields
            trade.stock_ticker = trade_update.stock_ticker
            trade.buy_price = trade_update.buy_price if trade_update.order_type == "buy" else trade.buy_price
            trade.quantity = trade_update.quantity
            trade.capital_used = trade_update.buy_price * trade_update.quantity if trade_update.order_type == "buy" else trade.capital_used
            trade.brokerage_charge = trade_update.brokerage_charge or trade.brokerage_charge or 0
            trade.mtf_charge = trade_update.mtf_charge or trade.mtf_charge or 0 if trade_update.type == "mtf" else 0
            trade.type = trade_update.type

        db.commit()
        db.refresh(trade)
        log_action("trade_updated", user, correlation_id, {
            "trade_id": trade_id,
            "stock_ticker": trade.stock_ticker,
            "status": trade.status,
            "broker": user.broker
        })
        return trade
    except Exception as e:
        log_error("update_trade_failed", e, current_user, correlation_id, {"trade_id": trade_id, "broker": user.broker})
        raise HTTPException(status_code=500, detail=f"Error updating trade: {str(e)}")

@router.get(
    "/trades",
    response_model=List[TradeOut]
)
async def list_trades(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), request: Request = None):
    """
    List all trades for the authenticated user.
    """
    correlation_id = await log_request(request, "list_trades", current_user)
    try:
        trades = db.query(Trade).options(selectinload(Trade.order)).filter(Trade.user_id == current_user.id).all()
        log_action("trades_listed", current_user, correlation_id, {"trade_count": len(trades)})
        return trades
    except Exception as e:
        log_error("list_trades_failed", e, current_user, correlation_id)
        raise HTTPException(status_code=500, detail=f"Error listing trades: {str(e)}")

def generate_zerodha_checksum(api_key: str, token: str, api_secret: str) -> str:
    """
    Generate checksum for Zerodha Kite Connect API session request or refresh.
    """
    from hashlib import sha256
    return sha256(f"{api_key}{token}{api_secret}".encode()).hexdigest()