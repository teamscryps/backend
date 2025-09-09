from models.user import User
from models.trade import Trade
from models.order import Order
from database import SessionLocal
import httpx
from kiteconnect import KiteConnect
try:
    from growwapi import GrowwAPI  # type: ignore
except ImportError:  # allow tests without growwapi
    GrowwAPI = None  # type: ignore
import upstox_client
from upstox_client.rest import ApiException
try:
    from icici_client import ICICIAPIClient
except ImportError:  # allow tests without icici_client
    ICICIAPIClient = None

def execute_bulk_trade(broker_type, stock_symbol, percent_quantity, user_ids):
    db = SessionLocal()
    results = []
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    
    for user in users:
        try:
            # Calculate capital to use
            capital_to_use = user.capital * (percent_quantity / 100)
            
            # Broker-specific logic with real API calls
            if broker_type == 'zerodha' and user.session_id and user.api_key:
                try:
                    kite = KiteConnect(api_key=user.api_key)
                    kite.set_access_token(user.session_id)
                    
                    # Get current market price for the stock
                    quote_data = kite.quote(f"NSE:{stock_symbol}")
                    current_price = quote_data.get(f"NSE:{stock_symbol}", {}).get("last_price", 0)
                    
                    # Calculate quantity based on capital and current price
                    quantity = int(capital_to_use / current_price) if current_price > 0 else 0
                    
                    # Place order through Zerodha
                    order_response = kite.place_order(
                        variety=kite.VARIETY_REGULAR,
                        exchange=kite.EXCHANGE_NSE,
                        tradingsymbol=stock_symbol,
                        transaction_type=kite.TRANSACTION_TYPE_BUY,
                        quantity=quantity,
                        product=kite.PRODUCT_CNC,
                        order_type=kite.ORDER_TYPE_MARKET
                    )
                    
                    buy_price = current_price
                    
                except Exception as e:
                    print(f"Zerodha API error for user {user.id}: {e}")
                    # Set default values when API fails
                    buy_price = 0
                    quantity = 0
                    
            elif broker_type == 'groww' and user.session_id and GrowwAPI is not None:
                try:
                    groww = GrowwAPI(user.session_id)
                    # Get current price and place order
                    # Note: Implement actual Groww API calls here
                    buy_price = 0  # To be set by actual API response
                    quantity = 0    # To be set by actual API response
                    
                except Exception as e:
                    print(f"Groww API error for user {user.id}: {e}")
                    buy_price = 0
                    quantity = 0
                    
            elif broker_type == 'icici' and user.session_id and user.api_key and ICICIAPIClient is not None:
                try:
                    icici = ICICIAPIClient(
                        api_key=user.api_key,
                        api_secret=user.api_secret,
                        access_token=user.session_id
                    )
                    
                    # Get current market price for the stock
                    quote_data = icici.get_quote(stock_symbol, "NSE")
                    current_price = quote_data.get('last_price', 0)
                    
                    # Calculate quantity based on capital and current price
                    quantity = int(capital_to_use / current_price) if current_price > 0 else 0
                    
                    if quantity > 0:
                        # Place order through ICICI
                        order_response = icici.place_order(
                            symbol=stock_symbol,
                            side="BUY",
                            quantity=quantity,
                            order_type="MARKET",
                            product="CNC",
                            exchange="NSE"
                        )
                        
                        buy_price = current_price
                    else:
                        buy_price = 0
                    
                except Exception as e:
                    print(f"ICICI API error for user {user.id}: {e}")
                    # Set default values when API fails
                    buy_price = 0
                    quantity = 0
                    
            else:
                # No valid broker session
                buy_price = 0
                quantity = 0
                
            # Create trade object with real or default values
            trade = Trade(
                stock_ticker=stock_symbol,
                buy_price=buy_price,
                quantity=quantity,
                capital_used=capital_to_use if quantity > 0 else 0,
                status='pending' if quantity > 0 else 'failed',
                type=None
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            results.append({'user_id': user.id, 'trade_id': trade.id, 'status': 'success' if quantity > 0 else 'failed'})
            
        except Exception as e:
            print(f"Error processing trade for user {user.id}: {e}")
            # Create failed trade record
            trade = Trade(
                stock_ticker=stock_symbol,
                buy_price=0,
                quantity=0,
                capital_used=0,
                status='failed',
                type=None
            )
            db.add(trade)
            db.commit()
            results.append({'user_id': user.id, 'trade_id': trade.id, 'status': 'failed', 'error': str(e)})
    
    db.close()
    return results 