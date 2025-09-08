from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from schemas.watchlist import WatchlistStockOut, WatchlistStockCreate
from typing import List
from kiteconnect import KiteConnect
import logging
import csv
import os

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

def load_stocks_from_csv():
    """Load stocks from CSV file"""
    stocks = {}
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'stocks.csv')
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Skip empty rows or rows without symbol
                if row.get('symbol') and row.get('stock'):
                    symbol = row['symbol'].replace('.NS', '')  # Remove .NS suffix for display
                    stocks[symbol] = {
                        "name": row['stock'],
                        "exchange": "NSE"
                    }
    except FileNotFoundError:
        logging.error(f"Stocks CSV file not found at {csv_path}")
        # Fallback to some basic stocks
        return {
            "RELIANCE": {"name": "Reliance Industries Ltd", "exchange": "NSE"},
            "TCS": {"name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
            "INFY": {"name": "Infosys Ltd", "exchange": "NSE"},
        }
    except Exception as e:
        logging.error(f"Error reading stocks CSV: {str(e)}")
        # Fallback to some basic stocks
        return {
            "RELIANCE": {"name": "Reliance Industries Ltd", "exchange": "NSE"},
            "TCS": {"name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
            "INFY": {"name": "Infosys Ltd", "exchange": "NSE"},
        }
    
    return stocks

# Load stocks from CSV on module import
STOCKS_DICT = load_stocks_from_csv()

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
    for i, (symbol, info) in enumerate(list(STOCKS_DICT.items())):  # Return all stocks from CSV
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
    if stock.symbol not in STOCKS_DICT:
        raise HTTPException(status_code=400, detail="Stock not found in our database")

    price_data = get_real_time_price(current_user, stock.symbol)

    return {
        "id": hash(stock.symbol) % 1000,  # Mock ID
        "symbol": stock.symbol,
        "name": STOCKS_DICT[stock.symbol]["name"],
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

    for symbol, info in STOCKS_DICT.items():
        if query_upper in symbol or query_upper in info["name"].upper():
            price_data = get_real_time_price(current_user, symbol)
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "currentPrice": price_data["currentPrice"],
                "changePercent": price_data["changePercent"]
            })

    return {"results": results[:10]}  # Return top 10 matches
