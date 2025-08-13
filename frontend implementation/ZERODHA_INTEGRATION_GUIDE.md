# Zerodha Integration Guide

## Overview
This guide explains how to properly connect your backend to Zerodha's Kite Connect API and get real data instead of mock data.

## Problem
Your backend was showing mock data because:
1. The `session_id` field was empty/null
2. The backend wasn't making actual API calls to Zerodha
3. The integration wasn't using the proper Kite Connect flow

## Solution
We've updated the backend to use the proper Zerodha Kite Connect integration. Here's the complete flow:

## Step-by-Step Integration

### Step 1: Install Dependencies
```bash
pip install kiteconnect==6.1.0
```

### Step 2: Set Up Zerodha API Credentials
First, set up your API credentials using the existing endpoint:

```http
POST /api/v1/auth/first-time-api-setup
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "api_key": "your_zerodha_api_key",
  "api_secret": "your_zerodha_api_secret",
  "broker": "zerodha"
}
```

### Step 3: Generate Zerodha Login URL
Get the login URL for user authentication:

```http
GET /api/v1/dashboard/zerodha/login-url
Authorization: Bearer <your_access_token>
```

**Response:**
```json
{
  "login_url": "https://kite.trade/connect/login?api_key=your_api_key&v=3",
  "message": "Open this URL in your browser to login to Zerodha. After login, you'll get a request_token to use for activation."
}
```

### Step 4: User Login to Zerodha
1. Open the `login_url` in a browser
2. Login with Zerodha credentials
3. You'll be redirected to your redirect URL with a `request_token` parameter
4. Extract the `request_token` from the URL

### Step 5: Activate Zerodha Brokerage
Use the `request_token` to activate your Zerodha connection:

```http
POST /api/v1/dashboard/activate-brokerage
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "brokerage": "zerodha",
  "api_url": "https://api.kite.trade",
  "api_key": "your_zerodha_api_key",
  "api_secret": "your_zerodha_api_secret",
  "request_token": "request_token_from_step_4"
}
```

**Response:**
```json
{
  "message": "zerodha activated successfully",
  "session_id": "your_access_token"
}
```

### Step 6: Verify Real Data
Now when you call the dashboard endpoint, you should get real data:

```http
GET /api/v1/dashboard/dashboard
Authorization: Bearer <your_access_token>
```

**Expected Response (Real Data):**
```json
{
  "activity_status": {
    "is_active": true,
    "last_active": "Aug 12, 2025 17:36:22"
  },
  "portfolio_overview": {
    "value": 50000.0,
    "change_percentage": 5.2
  },
  "unused_funds": 15000.0,
  "allocated_funds": 35000.0,
  "ongoing_trades": [
    {
      "stock": "RELIANCE",
      "bought": 2500.0,
      "quantity": 10,
      "capital_used": 25000.0,
      "profit": 500.0
    }
  ],
  "recent_trades": [...],
  "overall_profit": {
    "value": 2500.0,
    "percentage": 5.0,
    "last_7_days": [...]
  }
}
```

## What Changed in the Backend

### 1. Proper Kite Connect Integration
- Added `kiteconnect` package
- Uses `KiteConnect` class for API calls
- Proper session management with `generate_session()`

### 2. Real API Calls
Instead of mock data, the backend now makes real calls:
```python
# Get holdings
holdings_data = kite.holdings()
holdings = holdings_data.get("data", [])

# Get margins
margins_data = kite.margins()
equity_margins = margins_data.get("data", {}).get("equity", {})
unused_funds = equity_margins.get("available", {}).get("cash", 0)
allocated_funds = equity_margins.get("utilised", {}).get("debits", 0)
```

### 3. Session Management
- Stores encrypted `access_token` in `session_id`
- Stores encrypted `refresh_token` for token renewal
- Automatic session refresh when tokens expire

### 4. Error Handling
- Graceful fallback to placeholder data if API fails
- Proper error logging for debugging
- Session validation before API calls

## Troubleshooting

### Issue: Still seeing mock data
**Check:**
1. Is `user.session_id` populated? (Check logs for `"broker": "zerodha"`)
2. Are there any `zerodha_api_error` logs?
3. Did the activation succeed? (Look for `zerodha_session_created` logs)

### Issue: Activation fails
**Check:**
1. Is the `request_token` valid and recent?
2. Are API key and secret correct?
3. Check logs for `zerodha_session_creation_failed`

### Issue: API calls fail
**Check:**
1. Is the access token expired? (Tokens expire at midnight)
2. Are there network connectivity issues?
3. Check Zerodha's API status

## Log Monitoring

Watch for these log entries to verify proper integration:

**Successful Integration:**
- `zerodha_login_url_generated`
- `zerodha_session_created`
- `brokerage_activated`
- `zerodha_portfolio_fetched`

**Error Indicators:**
- `zerodha_session_creation_failed`
- `zerodha_api_error`
- `zerodha_api_fallback`

## Security Notes

1. **API Credentials**: All credentials are encrypted using Fernet
2. **Session Tokens**: Access tokens are encrypted before storage
3. **Token Expiry**: Access tokens expire daily at midnight
4. **Refresh Tokens**: Stored for automatic token renewal

## Next Steps

1. **Install the updated requirements**: `pip install -r requirements.txt`
2. **Set up your API credentials** using the first-time setup endpoint
3. **Generate login URL** and complete Zerodha authentication
4. **Activate brokerage** with the request token
5. **Verify real data** in the dashboard

Once completed, you should see real portfolio data, actual holdings, and live fund information instead of the placeholder values.
