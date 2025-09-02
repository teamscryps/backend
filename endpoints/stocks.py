from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from schemas.stock import StockOptionOut, StockDetailsOut
from typing import List
from kiteconnect import KiteConnect
import logging

router = APIRouter(prefix="/stocks", tags=["stocks"])

# Popular NSE stocks for trading
POPULAR_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "exchange": "NSE"},
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
    {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "exchange": "NSE"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "exchange": "NSE"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "exchange": "NSE"},
    {"symbol": "ITC", "name": "ITC Ltd", "exchange": "NSE"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "exchange": "NSE"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd", "exchange": "NSE"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd", "exchange": "NSE"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "exchange": "NSE"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "exchange": "NSE"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "exchange": "NSE"},
    {"symbol": "WIPRO", "name": "Wipro Ltd", "exchange": "NSE"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd", "exchange": "NSE"},
]

def get_real_market_data(user: UserModel, symbols: List[str]):
    """Fetch real market data from Zerodha if user has active session"""
    market_data = []

    if not user.api_key or not user.session_id or user.broker != "zerodha":
        # Return mock data if no active session
        for stock in POPULAR_STOCKS[:10]:  # Return first 10 stocks
            market_data.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "price": 100.0 + (hash(stock["symbol"]) % 900),  # Mock price
                "mtf_amount": (100.0 + (hash(stock["symbol"]) % 900)) * 20  # Mock MTF
            })
        return market_data

    try:
        kite = KiteConnect(api_key=user.api_key)
        kite.set_access_token(user.session_id)

        # Format symbols for Kite API
        kite_symbols = [f"NSE:{symbol}" for symbol in symbols]

        # Fetch quotes
        quotes = kite.quote(kite_symbols)

        for stock in POPULAR_STOCKS:
            symbol = stock["symbol"]
            kite_symbol = f"NSE:{symbol}"

            if kite_symbol in quotes:
                quote = quotes[kite_symbol]
                market_data.append({
                    "symbol": symbol,
                    "name": stock["name"],
                    "price": quote.get("last_price", 0),
                    "mtf_amount": quote.get("last_price", 0) * 20  # Approximate MTF amount
                })
            else:
                # Fallback to mock data for this stock
                market_data.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "price": 100.0 + (hash(stock["symbol"]) % 900),
                    "mtf_amount": (100.0 + (hash(stock["symbol"]) % 900)) * 20
                })

    except Exception as e:
        logging.error(f"Error fetching market data: {str(e)}")
        # Return mock data on error
        for stock in POPULAR_STOCKS[:10]:
            market_data.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "price": 100.0 + (hash(stock["symbol"]) % 900),
                "mtf_amount": (100.0 + (hash(stock["symbol"]) % 900)) * 20
            })

    return market_data

@router.get("/options", response_model=List[StockOptionOut])
def get_stock_options(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get list of available stocks with current market prices"""
    symbols = [stock["symbol"] for stock in POPULAR_STOCKS]
    market_data = get_real_market_data(current_user, symbols)

    return [StockOptionOut(**stock) for stock in market_data]

@router.get("/{symbol}", response_model=StockDetailsOut)
def get_stock_details(symbol: str, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get detailed information for a specific stock"""
    # Check if stock exists in our list
    stock_info = next((s for s in POPULAR_STOCKS if s["symbol"] == symbol.upper()), None)
    if not stock_info:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Try to get real market data
    if current_user.api_key and current_user.session_id and current_user.broker == "zerodha":
        try:
            kite = KiteConnect(api_key=current_user.api_key)
            kite.set_access_token(current_user.session_id)

            kite_symbol = f"NSE:{symbol.upper()}"
            quotes = kite.quote([kite_symbol])

            if kite_symbol in quotes:
                quote = quotes[kite_symbol]
                return StockDetailsOut(
                    symbol=symbol.upper(),
                    name=stock_info["name"],
                    price=quote.get("last_price", 0),
                    mtf_amount=quote.get("last_price", 0) * 20
                )
        except Exception as e:
            logging.error(f"Error fetching stock details: {str(e)}")

    # Fallback to mock data
    mock_price = 100.0 + (hash(symbol.upper()) % 900)
    return StockDetailsOut(
        symbol=symbol.upper(),
        name=stock_info["name"],
        price=mock_price,
        mtf_amount=mock_price * 20
    )
