# Frontend Zerodha Integration Guide

## Complete Frontend Implementation for Zerodha Activation

### Step 1: Update Your API Service
Make sure your `frontend-api-service.js` has the updated functions:

```javascript
// Get Zerodha login URL
export const getZerodhaLoginURL = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/dashboard/zerodha/login-url`, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to get Zerodha login URL');
    }
    
    return response.json();
};

// Complete Zerodha activation with request token
export const completeZerodhaIntegration = async (requestToken) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/auth/first-time-api-setup`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            api_key: 's0t4ipm0u66kk0jq',
            api_secret: 'w6e1pmu3hk8ouselodxrmci7htg31mqb',
            broker: 'zerodha',
            request_token: requestToken
        })
    });
    
    if (!response.ok) {
        throw new Error('Failed to complete Zerodha integration');
    }
    
    return response.json();
};
```

### Step 2: Create Zerodha Activation Component

```jsx
// components/ZerodhaActivation.jsx
import React, { useState, useEffect } from 'react';
import { getZerodhaLoginURL, completeZerodhaIntegration } from '../services/frontend-api-service';

const ZerodhaActivation = () => {
    const [loginUrl, setLoginUrl] = useState('');
    const [requestToken, setRequestToken] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState('');

    // Get Zerodha login URL on component mount
    useEffect(() => {
        const fetchLoginURL = async () => {
            try {
                setIsLoading(true);
                const response = await getZerodhaLoginURL();
                setLoginUrl(response.login_url);
                setStatus('Login URL generated successfully');
            } catch (error) {
                setStatus('Failed to get login URL: ' + error.message);
            } finally {
                setIsLoading(false);
            }
        };

        fetchLoginURL();
    }, []);

    const handleZerodhaLogin = () => {
        if (loginUrl) {
            // Open Zerodha login in new window
            window.open(loginUrl, '_blank', 'width=800,height=600');
        }
    };

    const handleCompleteActivation = async () => {
        if (!requestToken) {
            setStatus('Please enter the request token');
            return;
        }

        try {
            setIsLoading(true);
            await completeZerodhaIntegration(requestToken);
            setStatus('Zerodha activation completed successfully!');
            
            // Refresh dashboard data
            window.location.reload();
        } catch (error) {
            setStatus('Activation failed: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="zerodha-activation">
            <h2>Connect to Zerodha</h2>
            
            <div className="step-1">
                <h3>Step 1: Login to Zerodha</h3>
                <p>Click the button below to open Zerodha login page:</p>
                <button 
                    onClick={handleZerodhaLogin}
                    disabled={!loginUrl || isLoading}
                    className="btn btn-primary"
                >
                    {isLoading ? 'Loading...' : 'Login to Zerodha'}
                </button>
            </div>

            <div className="step-2">
                <h3>Step 2: Complete Activation</h3>
                <p>After login, you'll be redirected. Copy the request_token from the URL and paste it below:</p>
                
                <div className="input-group">
                    <input
                        type="text"
                        placeholder="Paste request_token here"
                        value={requestToken}
                        onChange={(e) => setRequestToken(e.target.value)}
                        className="form-control"
                    />
                    <button 
                        onClick={handleCompleteActivation}
                        disabled={!requestToken || isLoading}
                        className="btn btn-success"
                    >
                        {isLoading ? 'Activating...' : 'Complete Activation'}
                    </button>
                </div>
            </div>

            {status && (
                <div className={`alert ${status.includes('success') ? 'alert-success' : 'alert-info'}`}>
                    {status}
                </div>
            )}

            <div className="instructions">
                <h4>Instructions:</h4>
                <ol>
                    <li>Click "Login to Zerodha" button</li>
                    <li>Login with your Zerodha credentials:
                        <ul>
                            <li><strong>Client ID:</strong> NRA237</li>
                            <li><strong>Password:</strong> Ram@1433</li>
                            <li><strong>TOTP:</strong> Enter 6-digit code from your authenticator</li>
                        </ul>
                    </li>
                    <li>After successful login, you'll be redirected to a URL like:
                        <code>https://your-redirect-url.com?action=login&status=success&request_token=YOUR_TOKEN_HERE</code>
                    </li>
                    <li>Copy the <code>request_token</code> value from the URL</li>
                    <li>Paste it in the input field above</li>
                    <li>Click "Complete Activation"</li>
                </ol>
            </div>
        </div>
    );
};

export default ZerodhaActivation;
```

### Step 3: Update Your Dashboard Component

```jsx
// components/Dashboard.jsx
import React, { useState, useEffect } from 'react';
import { getDashboardData } from '../services/frontend-api-service';
import ZerodhaActivation from './ZerodhaActivation';

const Dashboard = () => {
    const [dashboardData, setDashboardData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [showZerodhaActivation, setShowZerodhaActivation] = useState(false);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            setIsLoading(true);
            const data = await getDashboardData();
            setDashboardData(data);
            
            // Show Zerodha activation if no broker is connected
            if (!data.broker || data.broker === 'null') {
                setShowZerodhaActivation(true);
            }
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
        } finally {
            setIsLoading(false);
        }
    };

    if (isLoading) {
        return <div>Loading dashboard...</div>;
    }

    return (
        <div className="dashboard">
            {showZerodhaActivation ? (
                <ZerodhaActivation />
            ) : (
                <div className="dashboard-content">
                    <h1>Dashboard</h1>
                    
                    <div className="portfolio-summary">
                        <h2>Portfolio Summary</h2>
                        <div className="funds">
                            <div className="fund-item">
                                <label>Available Funds:</label>
                                <span>₹{dashboardData?.unused_funds?.toLocaleString() || 0}</span>
                            </div>
                            <div className="fund-item">
                                <label>Allocated Funds:</label>
                                <span>₹{dashboardData?.allocated_funds?.toLocaleString() || 0}</span>
                            </div>
                        </div>
                    </div>

                    <div className="holdings">
                        <h2>Holdings ({dashboardData?.holdings?.length || 0})</h2>
                        {dashboardData?.holdings?.length > 0 ? (
                            <div className="holdings-list">
                                {dashboardData.holdings.map((holding, index) => (
                                    <div key={index} className="holding-item">
                                        <div className="symbol">{holding.tradingsymbol}</div>
                                        <div className="quantity">{holding.quantity} shares</div>
                                        <div className="avg-price">₹{holding.average_price}</div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p>No holdings found</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
```

### Step 4: Add CSS Styling

```css
/* styles/ZerodhaActivation.css */
.zerodha-activation {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
}

.step-1, .step-2 {
    margin-bottom: 30px;
    padding: 20px;
    border: 1px solid #ddd;
    border-radius: 8px;
}

.input-group {
    display: flex;
    gap: 10px;
    margin-top: 10px;
}

.input-group input {
    flex: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: bold;
}

.btn-primary {
    background-color: #007bff;
    color: white;
}

.btn-success {
    background-color: #28a745;
    color: white;
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.alert {
    padding: 15px;
    margin: 20px 0;
    border-radius: 4px;
}

.alert-success {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.alert-info {
    background-color: #d1ecf1;
    color: #0c5460;
    border: 1px solid #bee5eb;
}

.instructions {
    margin-top: 30px;
    padding: 20px;
    background-color: #f8f9fa;
    border-radius: 8px;
}

.instructions code {
    background-color: #e9ecef;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
}
```

## Complete Flow Summary

1. **User opens dashboard** → Sees Zerodha activation component
2. **Clicks "Login to Zerodha"** → Opens Zerodha login in new window
3. **Logs in with credentials** → Gets redirected with request_token
4. **Copies request_token** → Pastes in input field
5. **Clicks "Complete Activation"** → Backend stores access token
6. **Dashboard refreshes** → Shows real Zerodha data

## Testing the Complete Flow

1. **Run the backend:** `uvicorn main:app --reload`
2. **Start your frontend:** `npm start`
3. **Login to your app** with the test user
4. **Follow the Zerodha activation steps**
5. **Verify real data appears** in the dashboard

The integration is now complete and will fetch real data from Zerodha API instead of mock data!
