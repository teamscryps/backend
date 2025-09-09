# with/without MTF
#zerodha Buy
def zerodha_buy(trade_type, ticker, quantity):
    """
    takes trade type: MTF true or not
    ticker: symbol for stock
    quantity: number of equity stocks

    returns:
    sucess or fail status
    orderID

    """
    pass
#zerodha sell

# with/without MTF
#angelone_buy
#angelone_sell

# with/without MTF
# groww buy
# groww sell

# with/without MTF
# icici direct buy
def icici_buy(trade_type, ticker, quantity, api_key, api_secret, access_token):
    """
    ICICI buy function

    Args:
        trade_type: MTF true or false
        ticker: symbol for stock
        quantity: number of equity stocks
        api_key: ICICI API key
        api_secret: ICICI API secret
        access_token: ICICI access token

    Returns:
        dict: success status and order ID
    """
    try:
        from icici_client import ICICIAPIClient

        icici = ICICIAPIClient(api_key, api_secret, access_token)

        # Determine product type based on MTF
        product = "MTF" if trade_type else "CNC"

        order_response = icici.place_order(
            symbol=ticker,
            side="BUY",
            quantity=quantity,
            order_type="MARKET",
            product=product,
            exchange="NSE"
        )

        return {
            "success": True,
            "order_id": order_response.get("order_id"),
            "message": "ICICI buy order placed successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "order_id": None,
            "message": f"ICICI buy order failed: {str(e)}"
        }

# icici direct sell
def icici_sell(trade_type, ticker, quantity, api_key, api_secret, access_token):
    """
    ICICI sell function

    Args:
        trade_type: MTF true or false
        ticker: symbol for stock
        quantity: number of equity stocks
        api_key: ICICI API key
        api_secret: ICICI API secret
        access_token: ICICI access token

    Returns:
        dict: success status and order ID
    """
    try:
        from icici_client import ICICIAPIClient

        icici = ICICIAPIClient(api_key, api_secret, access_token)

        # Determine product type based on MTF
        product = "MTF" if trade_type else "CNC"

        order_response = icici.place_order(
            symbol=ticker,
            side="SELL",
            quantity=quantity,
            order_type="MARKET",
            product=product,
            exchange="NSE"
        )

        return {
            "success": True,
            "order_id": order_response.get("order_id"),
            "message": "ICICI sell order placed successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "order_id": None,
            "message": f"ICICI sell order failed: {str(e)}"
        }

