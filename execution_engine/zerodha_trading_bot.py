import time
import json
import logging
from datetime import datetime
from kiteconnect import KiteConnect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

class TradingBot:
    def __init__(self, api_key, access_token):
        """
        Initialize the trading bot

        Args:
            api_key (str): Zerodha API key
            access_token (str): Access token
        """
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

        # Trading parameters
        self.max_daily_loss = 5000
        self.max_position_value = 50000
        self.mtf_enabled = True

        # Track orders and positions
        self.active_orders = {}
        self.positions = {}

        logging.info("Trading bot initialized successfully")

    def get_ltp(self, instrument_token):
        """Get Last Traded Price"""
        try:
            ltp_data = self.kite.ltp([instrument_token])
            return ltp_data[str(instrument_token)]['last_price']
        except Exception as e:
            logging.error(f"Error getting LTP: {e}")
            return None

    def place_buy_order(self, symbol, exchange, qty, price=None, order_type="MARKET", 
                       product="CNC", use_mtf=False):
        """
        Place buy order with enhanced logic

        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange
            qty (int): Quantity
            price (float): Limit price (for LIMIT orders)
            order_type (str): Order type
            product (str): Product type
            use_mtf (bool): Use MTF for delivery orders

        Returns:
            str: Order ID if successful
        """
        try:
            # Use MTF for delivery orders if enabled
            if use_mtf and product == "CNC" and self.mtf_enabled:
                product = "MTF"
                logging.info(f"Using MTF for {symbol} buy order")

            order_id = self.kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type="BUY",
                quantity=qty,
                product=product,
                order_type=order_type,
                price=price,
                validity="DAY"
            )

            # Track the order
            self.active_orders[order_id] = {
                'symbol': symbol,
                'type': 'BUY',
                'quantity': qty,
                'product': product,
                'timestamp': datetime.now()
            }

            logging.info(f"Buy order placed: {symbol}, Qty: {qty}, OrderID: {order_id}")
            return order_id

        except Exception as e:
            logging.error(f"Error placing buy order for {symbol}: {e}")
            return None

    def place_sell_order(self, symbol, exchange, qty, price=None, order_type="MARKET", 
                        product="CNC"):
        """
        Place sell order

        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange
            qty (int): Quantity
            price (float): Limit price
            order_type (str): Order type
            product (str): Product type

        Returns:
            str: Order ID if successful
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type="SELL",
                quantity=qty,
                product=product,
                order_type=order_type,
                price=price,
                validity="DAY"
            )

            # Track the order
            self.active_orders[order_id] = {
                'symbol': symbol,
                'type': 'SELL',
                'quantity': qty,
                'product': product,
                'timestamp': datetime.now()
            }

            logging.info(f"Sell order placed: {symbol}, Qty: {qty}, OrderID: {order_id}")
            return order_id

        except Exception as e:
            logging.error(f"Error placing sell order for {symbol}: {e}")
            return None

    def place_stoploss_order(self, symbol, exchange, qty, trigger_price, 
                           product="CNC", order_type="SL-M"):
        """
        Place stop-loss order

        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange
            qty (int): Quantity
            trigger_price (float): Trigger price
            product (str): Product type
            order_type (str): SL or SL-M

        Returns:
            str: Order ID if successful
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type="SELL",
                quantity=qty,
                product=product,
                order_type=order_type,
                trigger_price=trigger_price,
                validity="DAY"
            )

            logging.info(f"Stop-loss order placed: {symbol}, Trigger: {trigger_price}, OrderID: {order_id}")
            return order_id

        except Exception as e:
            logging.error(f"Error placing stop-loss order for {symbol}: {e}")
            return None

    def update_positions(self):
        """Update current positions"""
        try:
            positions = self.kite.positions()
            self.positions = {}

            for position in positions['net']:
                if position['quantity'] != 0:
                    self.positions[position['tradingsymbol']] = position

            logging.info(f"Updated positions: {len(self.positions)} active positions")

        except Exception as e:
            logging.error(f"Error updating positions: {e}")

    def check_daily_pnl(self):
        """Check if daily loss limit is reached"""
        try:
            positions = self.kite.positions()
            total_pnl = sum(pos['pnl'] for pos in positions['net'])

            if total_pnl <= -self.max_daily_loss:
                logging.warning(f"Daily loss limit reached: {total_pnl}")
                return False
            return True

        except Exception as e:
            logging.error(f"Error checking daily P&L: {e}")
            return True

    def simple_momentum_strategy(self, symbol, exchange="NSE"):
        """
        Simple momentum-based trading strategy

        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange
        """
        try:
            # Get instrument token
            instruments = self.kite.instruments(exchange)
            instrument_token = None

            for instrument in instruments:
                if instrument['tradingsymbol'] == symbol:
                    instrument_token = instrument['instrument_token']
                    break

            if not instrument_token:
                logging.error(f"Instrument token not found for {symbol}")
                return

            # Get current price
            current_price = self.get_ltp(instrument_token)
            if not current_price:
                return

            # Get historical data (simple example)
            # In a real strategy, you would use proper technical indicators
            quote = self.kite.quote([instrument_token])
            ohlc = quote[str(instrument_token)]['ohlc']

            # Simple logic: Buy if current price > opening price by 1%
            if current_price > ohlc['open'] * 1.01:
                logging.info(f"{symbol}: Bullish signal detected")

                # Check if we don't already have a position
                if symbol not in self.positions:
                    # Place buy order
                    buy_order = self.place_buy_order(
                        symbol=symbol,
                        exchange=exchange,
                        qty=1,
                        order_type="MARKET",
                        product="MIS",  # Intraday
                        use_mtf=False
                    )

                    if buy_order:
                        # Place stop-loss at 2% below current price
                        stop_price = current_price * 0.98
                        self.place_stoploss_order(
                            symbol=symbol,
                            exchange=exchange,
                            qty=1,
                            trigger_price=stop_price,
                            product="MIS"
                        )

            # Simple sell logic: Sell if current price < opening price by 1%
            elif current_price < ohlc['open'] * 0.99:
                logging.info(f"{symbol}: Bearish signal detected")

                # If we have a long position, sell it
                if symbol in self.positions and self.positions[symbol]['quantity'] > 0:
                    self.place_sell_order(
                        symbol=symbol,
                        exchange=exchange,
                        qty=self.positions[symbol]['quantity'],
                        order_type="MARKET",
                        product="MIS"
                    )

        except Exception as e:
            logging.error(f"Error in momentum strategy for {symbol}: {e}")

    def mtf_investment_strategy(self, symbol, target_amount, exchange="NSE"):
        """
        MTF-based investment strategy

        Args:
            symbol (str): Trading symbol
            target_amount (float): Target investment amount
            exchange (str): Exchange
        """
        try:
            # Get current price
            instruments = self.kite.instruments(exchange)
            instrument_token = None

            for instrument in instruments:
                if instrument['tradingsymbol'] == symbol:
                    instrument_token = instrument['instrument_token']
                    break

            if not instrument_token:
                logging.error(f"Instrument token not found for {symbol}")
                return

            current_price = self.get_ltp(instrument_token)
            if not current_price:
                return

            # Calculate quantity based on target amount
            # Assuming 4x leverage with MTF (25% margin)
            margin_required = target_amount * 0.25
            total_investment = target_amount
            quantity = int(total_investment / current_price)

            if quantity > 0:
                logging.info(f"{symbol}: MTF investment - Qty: {quantity}, Amount: {total_investment}")

                # Place MTF buy order
                mtf_order = self.place_buy_order(
                    symbol=symbol,
                    exchange=exchange,
                    qty=quantity,
                    price=current_price,
                    order_type="LIMIT",
                    product="CNC",
                    use_mtf=True
                )

                if mtf_order:
                    logging.info(f"MTF order placed for {symbol}: {mtf_order}")

        except Exception as e:
            logging.error(f"Error in MTF strategy for {symbol}: {e}")

    def run_trading_session(self):
        """
        Main trading session loop
        """
        logging.info("Starting trading session...")

        # List of stocks to trade
        watchlist = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'SBIN']
        mtf_watchlist = ['RELIANCE', 'HDFC', 'SBIN']  # MTF eligible stocks

        session_start = datetime.now()

        try:
            while True:
                current_time = datetime.now()

                # Check if market is open (simplified check)
                if current_time.hour < 9 or current_time.hour >= 15:
                    logging.info("Market closed, waiting...")
                    time.sleep(300)  # Wait 5 minutes
                    continue

                # Check daily P&L limit
                if not self.check_daily_pnl():
                    logging.warning("Daily loss limit reached, stopping trading")
                    break

                # Update positions
                self.update_positions()

                # Run momentum strategy on watchlist
                for symbol in watchlist:
                    self.simple_momentum_strategy(symbol)
                    time.sleep(1)  # Small delay between stocks

                # Run MTF investment strategy (less frequent)
                if current_time.minute % 30 == 0:  # Every 30 minutes
                    for symbol in mtf_watchlist:
                        self.mtf_investment_strategy(symbol, 10000)  # 10k investment
                        time.sleep(1)

                # Log session statistics
                session_duration = current_time - session_start
                logging.info(f"Session running for: {session_duration}")

                # Wait before next iteration
                time.sleep(60)  # 1 minute interval

        except KeyboardInterrupt:
            logging.info("Trading session stopped by user")
        except Exception as e:
            logging.error(f"Error in trading session: {e}")

        logging.info("Trading session ended")

    def close_all_positions(self):
        """
        Emergency function to close all open positions
        """
        try:
            self.update_positions()

            for symbol, position in self.positions.items():
                if position['quantity'] > 0:  # Long position
                    self.place_sell_order(
                        symbol=symbol,
                        exchange=position['exchange'],
                        qty=position['quantity'],
                        order_type="MARKET",
                        product=position['product']
                    )
                elif position['quantity'] < 0:  # Short position
                    self.place_buy_order(
                        symbol=symbol,
                        exchange=position['exchange'],
                        qty=abs(position['quantity']),
                        order_type="MARKET",
                        product=position['product']
                    )

            logging.info("All positions closed")

        except Exception as e:
            logging.error(f"Error closing positions: {e}")

# Configuration and main execution
def main():
    """
    Main function to run the trading bot
    """
    # Configuration (replace with your actual credentials)
    config = {
        'api_key': 'your_api_key_here',
        'access_token': 'your_access_token_here'
    }

    # Validate configuration
    if config['api_key'] == 'your_api_key_here':
        print("Please update the configuration with your actual API credentials")
        return

    try:
        # Initialize trading bot
        bot = TradingBot(config['api_key'], config['access_token'])

        # Test connection
        profile = bot.kite.profile()
        logging.info(f"Connected as: {profile['user_name']}")

        # Run trading session
        bot.run_trading_session()

    except Exception as e:
        logging.error(f"Error starting trading bot: {e}")

if __name__ == "__main__":
    main()
