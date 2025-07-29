# Frontend Integration Guide

## 📁 Files Created

1. **`frontend-api-service.js`** - Complete API service with all endpoints
2. **`useApi.js`** - React hooks for easy integration

## 🚀 Quick Integration

### Step 1: Copy Files
Copy both files to your frontend project:
```bash
cp frontend-api-service.js /path/to/your/frontend/src/services/
cp useApi.js /path/to/your/frontend/src/hooks/
```

### Step 2: Import and Use

#### For React Components:
```javascript
import { useAuth, useDashboard } from './hooks/useApi';

function LoginComponent() {
    const { login, loading } = useAuth();
    
    const handleLogin = async (email, password) => {
        try {
            await login(email, password);
            // Redirect to dashboard
        } catch (error) {
            // Show error message
        }
    };
    
    return (
        <form onSubmit={handleLogin}>
            {/* Your existing login form */}
        </form>
    );
}

function DashboardComponent() {
    const { dashboardData, loading, error, fetchDashboardData } = useDashboard();
    
    useEffect(() => {
        fetchDashboardData();
    }, []);
    
    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;
    
    return (
        <div>
            <h1>Portfolio: ${dashboardData?.portfolio_overview?.value}</h1>
            {/* Your existing dashboard UI */}
        </div>
    );
}
```

#### For Vanilla JavaScript:
```javascript
import * as api from './services/frontend-api-service.js';

// Login
try {
    const userData = await api.signin('user@example.com', 'password');
    console.log('Logged in:', userData);
} catch (error) {
    console.error('Login failed:', error);
}

// Get Dashboard Data
try {
    const dashboardData = await api.getDashboardData();
    console.log('Dashboard:', dashboardData);
} catch (error) {
    console.error('Dashboard failed:', error);
}
```

## 🔧 Configuration

### Update API Base URL
If your backend runs on a different URL, update in `frontend-api-service.js`:
```javascript
const API_BASE_URL = 'http://your-backend-url:8000/api/v1';
```

### Environment Variables (Recommended)
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
```

## 📋 All Available Endpoints

| Function | Endpoint | Method | Auth Required |
|----------|----------|--------|---------------|
| `signup(email, password)` | `/auth/signup` | POST | No |
| `signin(email, password)` | `/auth/signin` | POST | No |
| `requestOTP(email)` | `/auth/request-otp` | POST | No |
| `otpLogin(email, otp)` | `/auth/otp-login` | POST | No |
| `logout()` | `/auth/logout` | POST | Yes |
| `getDashboardData()` | `/dashboard/dashboard` | GET | Yes |
| `activateBrokerage(data)` | `/dashboard/activate-brokerage` | POST | Yes |

## 🔐 Authentication Flow

1. **Login/Signup** → Get access & refresh tokens
2. **API Calls** → Automatically include Bearer token
3. **Token Expiry** → Auto-refresh with refresh token
4. **Logout** → Clear tokens from localStorage

## 🎯 Key Features

- ✅ **Automatic Token Management** - Stores/retrieves tokens automatically
- ✅ **Auto Token Refresh** - Handles expired tokens seamlessly  
- ✅ **Error Handling** - Proper error messages for all endpoints
- ✅ **Loading States** - Built-in loading indicators
- ✅ **TypeScript Ready** - Easy to add types

## 🧪 Testing

### Test Login:
```javascript
const { login } = useAuth();
await login('testuser@example.com', 'testpassword123');
```

### Test Dashboard:
```javascript
const { fetchDashboardData } = useDashboard();
const data = await fetchDashboardData();
console.log('Dashboard:', data);
```

### Test Brokerage Activation:
```javascript
const { activateBrokerage } = useDashboard();
const result = await activateBrokerage({
    brokerage: 'zerodha',
    api_url: 'https://api.kite.trade',
    api_key: 'your_key',
    api_secret: 'your_secret',
    request_token: 'your_token'
});
```

## ⚠️ Important Notes

1. **Backend Must Be Running** on `http://localhost:8000`
2. **Redis Must Be Running** for rate limiting
3. **CORS Must Be Configured** if frontend runs on different port
4. **HTTPS Required** in production

## 🔧 Troubleshooting

### "Connection refused"
- Check if backend server is running
- Verify API_BASE_URL is correct

### "401 Unauthorized"
- Check if user is logged in
- Verify token is valid
- Try logging in again

### "500 Internal Server Error"
- Check backend logs
- Verify Redis is running
- Check database connection

## 🎉 Success!

Your frontend now has complete access to all backend endpoints without any UI changes needed! 