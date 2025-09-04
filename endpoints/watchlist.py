from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from schemas.watchlist import WatchlistStockOut, WatchlistStockCreate
from typing import List
from kiteconnect import KiteConnect
import logging

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# Mock data for popular stocks that can be added to watchlist
POPULAR_STOCKS = {
    "RELIANCE": {"name": "Reliance Industries Ltd", "exchange": "NSE"},
    "TCS": {"name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
    "INFY": {"name": "Infosys Ltd", "exchange": "NSE"},
    "HDFCBANK": {"name": "HDFC Bank Ltd", "exchange": "NSE"},
    "ICICIBANK": {"name": "ICICI Bank Ltd", "exchange": "NSE"},
    "HINDUNILVR": {"name": "Hindustan Unilever Ltd", "exchange": "NSE"},
    "ITC": {"name": "ITC Ltd", "exchange": "NSE"},
    "KOTAKBANK": {"name": "Kotak Mahindra Bank Ltd", "exchange": "NSE"},
    "LT": {"name": "Larsen & Toubro Ltd", "exchange": "NSE"},
    "AXISBANK": {"name": "Axis Bank Ltd", "exchange": "NSE"},
    "MARUTI": {"name": "Maruti Suzuki India Ltd", "exchange": "NSE"},
    "BAJFINANCE": {"name": "Bajaj Finance Ltd", "exchange": "NSE"},
    "BHARTIARTL": {"name": "Bharti Airtel Ltd", "exchange": "NSE"},
    "WIPRO": {"name": "Wipro Ltd", "exchange": "NSE"},
    "ULTRACEMCO": {"name": "UltraTech Cement Ltd", "exchange": "NSE"},
}

def get_real_time_price(user: UserModel, symbol: str):
    """Get real-time price for a stock symbol"""
    if not user.api_key or not user.session_id or user.broker != "zerodha":
        # Return null values if no active session
        return {
            "currentPrice": None,
            "previousClose": None,
            "change": None,
            "changePercent": None,
            "high": None,
            "low": None,
            "volume": None
        }

    try:
        kite = KiteConnect(api_key=user.api_key)
        kite.set_access_token(user.session_id)

        kite_symbol = f"NSE:{symbol}"
        quotes = kite.quote([kite_symbol])

        if kite_symbol in quotes:
            quote = quotes[kite_symbol]
            last_price = quote.get("last_price", 0)
            prev_close = quote.get("ohlc", {}).get("close", last_price * 0.95)

            return {
                "currentPrice": last_price,
                "previousClose": prev_close,
                "change": last_price - prev_close,
                "changePercent": ((last_price - prev_close) / prev_close * 100) if prev_close > 0 else 0,
                "high": quote.get("ohlc", {}).get("high", last_price * 1.02),
                "low": quote.get("ohlc", {}).get("low", last_price * 0.98),
                "volume": str(quote.get("volume", 1200000))
            }
    except Exception as e:
        logging.error(f"Error fetching price for {symbol}: {str(e)}")

    # Return null values on error
    return {
        "currentPrice": None,
        "previousClose": None,
        "change": None,
        "changePercent": None,
        "high": None,
        "low": None,
        "volume": None
    }

@router.get("/", response_model=List[WatchlistStockOut])
def get_watchlist(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's watchlist with real-time prices"""
    # For now, return a default watchlist with popular stocks
    # In a real implementation, you'd store user-specific watchlists in the database

    watchlist_stocks = []
    for i, (symbol, info) in enumerate(list(POPULAR_STOCKS.items())[:10]):  # Return first 10 stocks
        price_data = get_real_time_price(current_user, symbol)

        watchlist_stocks.append({
            "id": i + 1,
            "symbol": symbol,
            "name": info["name"],
            "currentPrice": price_data["currentPrice"],
            "previousClose": price_data["previousClose"],
            "change": price_data["change"],
            "changePercent": price_data["changePercent"],
            "high": price_data["high"],
            "low": price_data["low"],
            "volume": price_data["volume"]
        })

    return watchlist_stocks

@router.post("/", response_model=WatchlistStockOut)
def add_to_watchlist(stock: WatchlistStockCreate, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a stock to user's watchlist"""
    if stock.symbol not in POPULAR_STOCKS:
        raise HTTPException(status_code=400, detail="Stock not found in our database")

    price_data = get_real_time_price(current_user, stock.symbol)

    return {
        "id": hash(stock.symbol) % 1000,  # Mock ID
        "symbol": stock.symbol,
        "name": POPULAR_STOCKS[stock.symbol]["name"],
        "currentPrice": price_data["currentPrice"],
        "previousClose": price_data["previousClose"],
        "change": price_data["change"],
        "changePercent": price_data["changePercent"],
        "high": price_data["high"],
        "low": price_data["low"],
        "volume": price_data["volume"]
    }

@router.delete("/{stock_id}")
def remove_from_watchlist(stock_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a stock from user's watchlist"""
    # In a real implementation, you'd remove from database
    return {"message": f"Stock with ID {stock_id} removed from watchlist"}

@router.get("/search/{query}")
def search_stocks(query: str, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Search for stocks to add to watchlist"""
    query_upper = query.upper()
    results = []

    for symbol, info in POPULAR_STOCKS.items():
        if query_upper in symbol or query_upper in info["name"].upper():
            price_data = get_real_time_price(current_user, symbol)
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "currentPrice": price_data["currentPrice"],
                "changePercent": price_data["changePercent"]
            })

    return {"results": results[:10]}  # Return top 10 matches
