from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from schemas.stock import StockOptionOut, StockDetailsOut
from typing import List
from kiteconnect import KiteConnect
import logging
import csv
import os

router = APIRouter(prefix="/stocks", tags=["stocks"])

def load_stocks_from_csv():
    """Load stocks from CSV file"""
    stocks = []
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'stocks.csv')
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Skip empty rows or rows without symbol
                if row.get('symbol') and row.get('stock'):
                    stocks.append({
                        "symbol": row['symbol'].replace('.NS', ''),  # Remove .NS suffix for display
                        "name": row['stock'],
                        "exchange": "NSE"
                    })
    except FileNotFoundError:
        logging.error(f"Stocks CSV file not found at {csv_path}")
        # Fallback to hardcoded stocks if CSV not found
        return [
            {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "exchange": "NSE"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
            {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE"},
        ]
    except Exception as e:
        logging.error(f"Error reading stocks CSV: {str(e)}")
        # Fallback to hardcoded stocks on error
        return [
            {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "exchange": "NSE"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "exchange": "NSE"},
            {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE"},
        ]
    
    return stocks

# Load stocks from CSV on module import
STOCKS_DATA = load_stocks_from_csv()

def get_real_market_data(user: UserModel, symbols: List[str]):
    """Fetch real market data from Zerodha if user has active session"""
    market_data = []

    if not user.api_key or not user.session_id or user.broker != "zerodha":
        # Return null values if no active session
        for stock in STOCKS_DATA:  # Return all stocks from CSV
            market_data.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "price": None,
                "mtf_amount": None
            })
        return market_data

    try:
        kite = KiteConnect(api_key=user.api_key)
        kite.set_access_token(user.session_id)

        # Format symbols for Kite API
        kite_symbols = [f"NSE:{symbol}" for symbol in symbols]

        # Fetch quotes
        quotes = kite.quote(kite_symbols)

        for stock in STOCKS_DATA:
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
                # Return null values for this stock
                market_data.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "price": None,
                    "mtf_amount": None
                })

    except Exception as e:
        logging.error(f"Error fetching market data: {str(e)}")
        # Return null values on error
        for stock in STOCKS_DATA:  # Return all stocks from CSV
            market_data.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "price": None,
                "mtf_amount": None
            })

    return market_data

@router.get("/options", response_model=List[StockOptionOut])
def get_stock_options(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get list of available stocks with current market prices"""
    symbols = [stock["symbol"] for stock in STOCKS_DATA]
    market_data = get_real_market_data(current_user, symbols)

    return [StockOptionOut(**stock) for stock in market_data]

@router.get("/{symbol}", response_model=StockDetailsOut)
def get_stock_details(symbol: str, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get detailed information for a specific stock"""
    # Check if stock exists in our list
    stock_info = next((s for s in STOCKS_DATA if s["symbol"] == symbol.upper()), None)
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
