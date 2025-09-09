# ICICI Direct Integration Guide

This document explains how to integrate ICICI Direct brokerage with the trading backend.

## Overview

The ICICI Direct integration allows users to place orders, get quotes, and manage their portfolio through the ICICI Direct API.

## Setup

### 1. API Credentials

To use ICICI Direct API, you need:
- API Key
- API Secret
- Access Token

### 2. User Setup

Users can set up their ICICI credentials through the `/api/v1/first-time-api-setup` endpoint:

```json
{
  "api_key": "your_icici_api_key",
  "api_secret": "your_icici_api_secret",
  "broker": "icici",
  "request_token": "your_access_token"
}
```

### 3. Authentication

The ICICI client handles OAuth2 authentication. The access token should be obtained from ICICI's authentication flow and stored as `request_token` during setup.

## API Methods

### Initialize Client

```python
from icici_client import ICICIAPIClient

client = ICICIAPIClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    access_token="your_access_token"
)
```

### Get Quote

```python
quote = client.get_quote("RELIANCE", "NSE")
print(quote)
```

### Place Order

```python
order = client.place_order(
    symbol="RELIANCE",
    side="BUY",
    quantity=10,
    order_type="MARKET",
    product="CNC",
    exchange="NSE"
)
print(order)
```

### Get Order Status

```python
status = client.get_order_status("order_id")
print(status)
```

### Cancel Order

```python
result = client.cancel_order("order_id")
print(result)
```

### Get Portfolio

```python
portfolio = client.get_portfolio()
print(portfolio)
```

## Integration Points

### 1. Bulk Trade Execution

The ICICI integration is automatically used when `broker_type='icici'` is passed to the bulk trade execution endpoint.

### 2. Buy/Sell Logic

Use the `icici_buy()` and `icici_sell()` functions from `execution_engine/buy_sell_logic.py`:

```python
from execution_engine.buy_sell_logic import icici_buy, icici_sell

# Buy order
result = icici_buy(
    trade_type=False,  # MTF or not
    ticker="RELIANCE",
    quantity=10,
    api_key="your_api_key",
    api_secret="your_api_secret",
    access_token="your_access_token"
)

# Sell order
result = icici_sell(
    trade_type=False,
    ticker="RELIANCE",
    quantity=10,
    api_key="your_api_key",
    api_secret="your_api_secret",
    access_token="your_access_token"
)
```

## Error Handling

The ICICI client includes comprehensive error handling:
- Network errors
- Authentication failures
- API rate limits
- Invalid parameters

All errors are logged and appropriate exceptions are raised.

## Testing

To test the integration without making real API calls, you can:

1. Use the ICICI sandbox environment (if available)
2. Mock the API responses
3. Use test credentials

## Dependencies

Make sure to install the required dependencies:

```bash
pip install requests
```

## Notes

- The base URL is set to `https://api.icicidirect.com` - update if ICICI provides a different endpoint
- The client uses Bearer token authentication
- All API calls include proper error handling and logging
- The integration follows the same pattern as other brokers in the system</content>
<parameter name="filePath">/Users/apple/Desktop/backend/ICICI_INTEGRATION_GUIDE.md
