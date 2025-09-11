# ICICI Direct Integration Guide

## Overview
This guide explains how to properly connect your backend to ICICI Direct API and get real data instead of mock data.

## Problem
Your backend was showing mock data because:
1. The `session_id` field was empty/null
2. The backend wasn't making actual API calls to ICICI Direct
3. The integration wasn't using the proper OAuth2 flow

## Solution
We've updated the backend to use the proper ICICI Direct OAuth2 integration. Here's the complete flow:

## Step-by-Step Integration

### Step 1: Install Dependencies
```bash
pip install httpx
```

### Step 2: Set Up ICICI Direct API Credentials
First, set up your API credentials using the existing endpoint:

```http
POST /api/v1/auth/first-time-api-setup
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "api_key": "your_icici_api_key",
  "api_secret": "your_icici_api_secret",
  "broker": "icici"
}
```

### Step 3: Generate ICICI Direct Authorization URL
Get the authorization URL for user authentication:

```http
POST /api/v1/dashboard/icici/login-url
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "api_key": "your_icici_api_key",
  "redirect_uri": "http://localhost:3000/icici/callback"
}
```

**Response:**
```json
{
  "login_url": "https://api.icicidirect.com/oauth/authorize?client_id=your_api_key&redirect_uri=http://localhost:3000/icici/callback&response_type=code&scope=trading&state=user_123_abc12345",
  "redirect_uri": "http://localhost:3000/icici/callback",
  "message": "Open this URL in your browser to authorize ICICI Direct. After authorization, you'll be redirected with an authorization code.",
  "instructions": [
    "1. Click the login URL to open ICICI Direct authorization page",
    "2. Login with your ICICI Direct credentials",
    "3. Grant trading permissions to the application",
    "4. After successful authorization, you'll be redirected with authorization code",
    "5. Copy the authorization code from the redirect URL",
    "6. Use the authorization code to complete the activation"
  ]
}
```

### Step 4: User Authorization to ICICI Direct
1. Open the `login_url` in a browser
2. Login with ICICI Direct credentials
3. Grant trading permissions to the application
4. You'll be redirected to your redirect URL with an `code` parameter
5. Extract the `code` (authorization code) from the URL

### Step 5: Activate ICICI Direct Brokerage
Use the `authorization_code` to activate your ICICI Direct connection:

```http
POST /api/v1/dashboard/activate-brokerage
Authorization: Bearer <your_access_token>
Content-Type: application/json

{
  "brokerage": "icici",
  "api_url": "https://api.icicidirect.com",
  "api_key": "your_icici_api_key",
  "api_secret": "your_icici_api_secret",
  "authorization_code": "authorization_code_from_step_4",
  "redirect_uri": "http://localhost:3000/icici/callback"
}
```

**Response:**
```json
{
  "message": "icici activated successfully",
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

### 1. Proper ICICI Direct OAuth2 Integration
- Added `httpx` for async HTTP requests
- Uses standard OAuth2 authorization code flow
- Proper token exchange and storage

### 2. Real API Calls
Instead of mock data, the backend now makes real calls:
```python
# Exchange authorization code for access token
async with httpx.AsyncClient() as client:
    token_url = "https://api.icicidirect.com/oauth/token"
    token_data = {
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'client_id': api_key,
        'client_secret': api_secret,
        'redirect_uri': redirect_uri
    }

    response = await client.post(token_url, data=token_data)
    token_response = response.json()
    access_token = token_response.get('access_token')
```

### 3. Session Management
- Stores encrypted `access_token` in `session_id`
- Stores encrypted `refresh_token` for token renewal
- Automatic token refresh when tokens expire

### 4. Error Handling
- Graceful fallback to placeholder data if API fails
- Proper error logging for debugging
- Session validation before API calls

## Troubleshooting

### Issue: Still seeing mock data
**Check:**
1. Is `user.session_id` populated? (Check logs for `"broker": "icici"`)
2. Are there any `icici_api_error` logs?
3. Did the activation succeed? (Look for `icici_session_created` logs)

### Issue: Authorization fails
**Check:**
1. Is the `authorization_code` valid and recent?
2. Are API key and secret correct?
3. Check logs for `icici_session_creation_failed`

### Issue: API calls fail
**Check:**
1. Is the access token expired? (Tokens expire ~1-2 hours)
2. Are there network connectivity issues?
3. Check ICICI Direct's API status

## Log Monitoring

Watch for these log entries to verify proper integration:

**Successful Integration:**
- `icici_login_url_generated`
- `icici_session_created`
- `brokerage_activated`
- `icici_portfolio_fetched`

**Error Indicators:**
- `icici_session_creation_failed`
- `icici_api_error`
- `icici_api_fallback`

## Security Notes

1. **API Credentials**: All credentials are encrypted using Fernet
2. **Session Tokens**: Access tokens are encrypted before storage
3. **Token Expiry**: Access tokens expire after ~1-2 hours
4. **Refresh Tokens**: Stored for automatic token renewal

## Next Steps

1. **Install the updated requirements**: `pip install -r requirements.txt`
2. **Set up your API credentials** using the first-time setup endpoint
3. **Generate authorization URL** and complete ICICI Direct OAuth
4. **Activate brokerage** with the authorization code
5. **Verify real data** in the dashboard

Once completed, you should see real portfolio data, actual holdings, and live fund information instead of the placeholder values.

## Frontend Integration

### Updated API Service Functions

```javascript
// ICICI Integration Functions
export const getICICILoginURL = async (apiKey, redirectUri) => {
  const response = await fetch(`${API_BASE_URL}/dashboard/icici/login-url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`,
    },
    body: JSON.stringify({
      api_key: apiKey,
      redirect_uri: redirectUri
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to generate ICICI login URL');
  }

  const data = await response.json();
  return data;
};

export const completeICICIIntegration = async (apiKey, apiSecret) => {
  try {
    // Step 1: Set up API credentials
    await setupAPICredentials({
      api_key: apiKey,
      api_secret: apiSecret,
      broker: 'icici'
    });

    // Step 2: Get authorization URL
    const loginURLData = await getICICILoginURL(apiKey, window.location.origin + '/icici/callback');

    return {
      success: true,
      login_url: loginURLData.login_url,
      message: loginURLData.message
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};

export const activateICICIWithCode = async (apiKey, apiSecret, authorizationCode, redirectUri) => {
  try {
    const result = await activateBrokerage({
      brokerage: 'icici',
      api_url: 'https://api.icicidirect.com',
      api_key: apiKey,
      api_secret: apiSecret,
      authorization_code: authorizationCode,
      redirect_uri: redirectUri
    });

    return {
      success: true,
      message: result.message,
      access_token: result.access_token
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
};
```

### Updated API Setup Modal

```html
<div class="api-setup-modal">
  <h2>Welcome! Please set up your trading account</h2>
  <form id="api-setup-form">
    <div class="form-group">
      <label for="broker">Broker *</label>
      <select name="broker" required>
        <option value="">Select Broker</option>
        <option value="zerodha">Zerodha</option>
        <option value="groww">Groww</option>
        <option value="upstox">Upstox</option>
        <option value="icici">ICICI Direct</option>
      </select>
    </div>

    <div class="form-group">
      <label for="api_key">API Key *</label>
      <input type="text" name="api_key" placeholder="API Key" required />
    </div>

    <div class="form-group">
      <label for="api_secret">API Secret *</label>
      <input type="password" name="api_secret" placeholder="API Secret" required />
    </div>

    <!-- ICICI specific -->
    <div id="icici-fields" style="display: none;">
      <div class="form-group">
        <label for="authorization_code">Authorization Code (Optional - will be generated)</label>
        <input type="text" name="authorization_code" placeholder="Authorization Code from ICICI OAuth" />
        <small>Leave empty to generate authorization URL first</small>
      </div>
    </div>

    <button type="submit">Set Up Account</button>
  </form>
</div>
```

### Updated Form Handling

```javascript
// Handle form submission - Updated for ICICI OAuth flow
document.getElementById('api-setup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  const broker = formData.get('broker');

  try {
    if (broker === 'icici') {
      // ICICI OAuth flow
      const apiKey = formData.get('api_key');
      const apiSecret = formData.get('api_secret');
      const authorizationCode = formData.get('authorization_code');

      if (authorizationCode) {
        // Direct activation with authorization code
        const activationResult = await activateICICIWithCode(apiKey, apiSecret, authorizationCode, window.location.origin + '/icici/callback');
        if (activationResult.success) {
          alert('ICICI Direct activated successfully!');
          document.querySelector('.api-setup-modal').remove();
          window.location.href = '/dashboard';
        } else {
          alert('ICICI Direct activation failed: ' + activationResult.error);
        }
      } else {
        // Generate authorization URL first
        const setupResult = await completeICICIIntegration(apiKey, apiSecret);
        if (setupResult.success) {
          // Open authorization URL
          window.open(setupResult.login_url, '_blank');
          alert('ICICI Direct authorization URL opened. Please authorize the application and copy the authorization code from the redirect URL, then submit this form again with the code.');
        } else {
          alert('Failed to generate ICICI Direct authorization URL: ' + setupResult.error);
        }
      }
    } else {
      // Other brokers - existing flow
      // ... existing code ...
    }
  } catch (error) {
    console.error('API setup failed:', error);
    alert('Failed to set up API credentials: ' + error.message);
  }
});
```</content>
<parameter name="filePath">/Users/apple/Desktop/backend/frontend implementation/ICICI_INTEGRATION_GUIDE.md
