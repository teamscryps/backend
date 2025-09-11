# Frontend Integration Guide

## Overview
This guide shows how to integrate your frontend with the updated backend API, including the new Zerodha integration flow.

## Updated API Endpoints

### Authentication Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/signup` | POST | User registration |
| `/api/v1/auth/signin` | POST | User login |
| `/api/v1/auth/register` | POST | Registration with auto-generated password |
| `/api/v1/auth/forgot-password` | POST | Send password reset OTP |
| `/api/v1/auth/reset-password` | POST | Reset password using OTP |
| `/api/v1/auth/request-otp` | POST | Request OTP for login |
| `/api/v1/auth/otp-login` | POST | Login using OTP |
| `/api/v1/auth/check-api-setup` | GET | Check if API credentials set |
| `/api/v1/auth/first-time-api-setup` | POST | Set up API credentials first time |
| `/api/v1/auth/update-api-credentials` | POST | Update existing API credentials |
| `/api/v1/auth/api-credentials-info` | GET | Get information about API credentials |
| `/api/v1/auth/refresh` | POST | Refresh access token |
| `/api/v1/auth/logout` | POST | Logout user |

### Dashboard Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dashboard/dashboard` | GET | Get dashboard data (now with real Zerodha data) |
| `/api/v1/dashboard/activate-brokerage` | POST | Activate brokerage account |
| `/api/v1/dashboard/zerodha/login-url` | GET | **NEW** - Generate Zerodha login URL |
| `/api/v1/dashboard/order/buy` | POST | Place buy order |
| `/api/v1/dashboard/order/sell` | POST | Place sell order |

### Trade Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/trade/trades` | GET | Get all trades |
| `/api/v1/trade/trade` | POST | Create new trade |
| `/api/v1/trade/trade/{trade_id}` | GET | Get specific trade |
| `/api/v1/trade/trade/{trade_id}` | PUT | Update trade |

## Updated Frontend API Service

The `frontend-api-service.js` has been updated with new functions for the improved Zerodha integration:

### New Zerodha Integration Functions

```javascript
// Generate Zerodha Login URL
export const getZerodhaLoginURL = async () => {
    const response = await apiCall('/dashboard/zerodha/login-url', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to generate Zerodha login URL');
};

// Complete Zerodha integration flow
export const completeZerodhaIntegration = async (apiKey, apiSecret) => {
    try {
        // Step 1: Set up API credentials
        await setupAPICredentials({
            api_key: apiKey,
            api_secret: apiSecret,
            broker: 'zerodha'
        });
        
        // Step 2: Get login URL
        const loginURLData = await getZerodhaLoginURL();
        
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

// Activate Zerodha with request token
export const activateZerodhaWithToken = async (apiKey, apiSecret, requestToken) => {
    try {
        const result = await activateBrokerage({
            brokerage: 'zerodha',
            api_url: 'https://api.kite.trade',
            api_key: apiKey,
            api_secret: apiSecret,
            request_token: requestToken
        });
        
        return {
            success: true,
            message: result.message,
            session_id: result.session_id
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
};
```

## Updated Zerodha Integration Flow

### Step 1: Set up API Credentials and Get Login URL
```javascript
// Complete Zerodha Integration Flow
try {
    // Step 1: Set up credentials and get login URL
    const setupResult = await completeZerodhaIntegration('your_api_key', 'your_api_secret');
    if (setupResult.success) {
        // Open login URL in new window/tab
        window.open(setupResult.login_url, '_blank');
        
        // Show instructions to user
        alert('Please login to Zerodha and copy the request_token from the redirect URL');
    }
} catch (error) {
    console.error('Zerodha setup failed:', error);
}
```

### Step 2: Activate with Request Token
```javascript
// Step 2: Activate with request token (after user gets it from Zerodha)
try {
    const activationResult = await activateZerodhaWithToken('your_api_key', 'your_api_secret', 'request_token_from_zerodha');
    if (activationResult.success) {
        console.log('Zerodha activated successfully!');
        // Refresh dashboard to show real data
        const dashboardData = await getDashboardData();
        console.log('Real dashboard data:', dashboardData);
    }
} catch (error) {
    console.error('Zerodha activation failed:', error);
}
```

### Step 3: Get Real Dashboard Data
```javascript
// Get Dashboard Data (now with real Zerodha data)
try {
    const dashboardData = await getDashboardData();
    console.log('Dashboard data:', dashboardData);
    // Update UI with dashboard data
} catch (error) {
    console.error('Failed to fetch dashboard:', error);
    // Show error message to user
}
```

## Updated API Setup Modal

The API setup modal should now handle the new Zerodha flow:

```javascript
const showAPISetupModal = () => {
  const modal = `
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
        
        <!-- Zerodha specific - Updated for new flow -->
        <div id="zerodha-fields" style="display: none;">
          <div class="form-group">
            <label for="request_token">Request Token (Optional - will be generated)</label>
            <input type="text" name="request_token" placeholder="Request Token from Zerodha login" />
            <small>Leave empty to generate login URL first</small>
          </div>
        </div>
        
        <!-- Groww specific -->
        <div id="groww-fields" style="display: none;">
          <div class="form-group">
            <label for="totp_secret">TOTP Secret</label>
            <input type="text" name="totp_secret" placeholder="TOTP Secret" />
          </div>
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
  `;
  
  document.body.insertAdjacentHTML('beforeend', modal);
  
  // Handle broker selection to show/hide specific fields
  document.querySelector('select[name="broker"]').addEventListener('change', (e) => {
    const broker = e.target.value;
    
    // Hide all broker-specific fields
    document.getElementById('zerodha-fields').style.display = 'none';
    document.getElementById('groww-fields').style.display = 'none';
    document.getElementById('upstox-fields').style.display = 'none';
    document.getElementById('icici-fields').style.display = 'none';
    
    // Show relevant fields based on broker
    if (broker === 'zerodha') {
      document.getElementById('zerodha-fields').style.display = 'block';
    } else if (broker === 'groww') {
      document.getElementById('groww-fields').style.display = 'block';
    } else if (broker === 'upstox') {
      document.getElementById('upstox-fields').style.display = 'block';
    } else if (broker === 'icici') {
      document.getElementById('icici-fields').style.display = 'block';
    }
  });
  
  // Handle form submission - Updated for new Zerodha flow
  document.getElementById('api-setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const broker = formData.get('broker');
    
    try {
      if (broker === 'zerodha') {
        // New Zerodha flow
        const apiKey = formData.get('api_key');
        const apiSecret = formData.get('api_secret');
        const requestToken = formData.get('request_token');
        
        if (requestToken) {
          // Direct activation with request token
          const activationResult = await activateZerodhaWithToken(apiKey, apiSecret, requestToken);
          if (activationResult.success) {
            alert('Zerodha activated successfully!');
            document.querySelector('.api-setup-modal').remove();
            window.location.href = '/dashboard';
          } else {
            alert('Zerodha activation failed: ' + activationResult.error);
          }
        } else {
          // Generate login URL first
          const setupResult = await completeZerodhaIntegration(apiKey, apiSecret);
          if (setupResult.success) {
            // Open login URL
            window.open(setupResult.login_url, '_blank');
            alert('Zerodha login URL opened. Please login and copy the request_token from the redirect URL, then submit this form again with the token.');
          } else {
            alert('Failed to generate Zerodha login URL: ' + setupResult.error);
          }
        }
      } else if (broker === 'icici') {
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
    } catch (error) {
      console.error('API setup failed:', error);
      alert('Failed to set up API credentials: ' + error.message);
    }
  });
};
```

## Key Changes Summary

1. **New Endpoint**: `/api/v1/dashboard/zerodha/login-url` - Generates Zerodha login URL
2. **Updated Flow**: Zerodha integration now uses proper Kite Connect flow
3. **Real Data**: Dashboard now returns real Zerodha data instead of mock data
4. **Helper Functions**: Added `completeZerodhaIntegration()` and `activateZerodhaWithToken()`
5. **Improved UX**: Better error handling and user guidance

## Expected Results

After implementing these changes:
- ✅ Real portfolio data from Zerodha
- ✅ Actual holdings and positions
- ✅ Live fund information
- ✅ No more placeholder `unused_funds = 2300`
- ✅ Proper session management
- ✅ Automatic token refresh

The frontend will now work seamlessly with the updated backend to provide real Zerodha data instead of mock data. 