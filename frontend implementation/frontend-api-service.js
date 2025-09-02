// Frontend API Service - Complete Backend Integration
// This file handles all API calls to your FastAPI backend

const API_BASE_URL = 'http://localhost:8000/api/v1';

// Helper function to get stored token
const getAuthToken = () => {
    return localStorage.getItem('access_token');
};

// Helper function to get refresh token
const getRefreshToken = () => {
    return localStorage.getItem('refresh_token');
};

// Helper function to store tokens
const storeTokens = (accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
};

// Helper function to clear tokens
const clearTokens = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
};

// Helper function for API calls with authentication
const apiCall = async (endpoint, options = {}) => {
    const token = getAuthToken();
    
    const config = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` }),
            ...options.headers
        },
        ...options
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        
        // Handle token refresh if 401
        if (response.status === 401) {
            const refreshed = await refreshAccessToken();
            if (refreshed) {
                // Retry the original request with new token
                const newToken = getAuthToken();
                config.headers.Authorization = `Bearer ${newToken}`;
                return await fetch(`${API_BASE_URL}${endpoint}`, config);
            }
        }
        
        return response;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
};

// Helper function to parse URL parameters
const getUrlParameter = (name) => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
};

// Check if we have a request_token in URL (after Zerodha redirect)
const hasZerodhaRequestToken = () => {
    return getUrlParameter('request_token') !== null;
};

// Get request token from URL
const getZerodhaRequestToken = () => {
    return getUrlParameter('request_token');
};

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

// Check if user has API credentials set up
export const checkAPISetup = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/auth/check-api-setup`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to check API setup');
    }
    
    return response.json();
};

// Setup API credentials for the first time
export const setupAPICredentials = async (credentials) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/auth/first-time-api-setup`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(credentials)
    });
    
    if (!response.ok) {
        throw new Error('Failed to setup API credentials');
    }
    
    return response.json();
};

// Get dashboard data
export const getDashboardData = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/dashboard/dashboard`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
    }
    
    return response.json();
};

// User registration
export const registerUser = async (userData) => {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
    });
    
    if (!response.ok) {
        throw new Error('Registration failed');
    }
    
    return response.json();
};

// User login
export const loginUser = async (credentials) => {
    const formData = new URLSearchParams();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);
    
    const response = await fetch(`${API_BASE_URL}/auth/signin`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: formData
    });
    
    if (!response.ok) {
        throw new Error('Login failed');
    }
    
    const data = await response.json();
    storeTokens(data.access_token, data.refresh_token);
    return data;
};

// User signup (with password)
export const signupUser = async (userData) => {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
    });
    
    if (!response.ok) {
        throw new Error('Signup failed');
    }
    
    const data = await response.json();
    storeTokens(data.access_token, data.refresh_token);
    return data;
};

// Get all trades
export const getTrades = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/trades`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch trades');
    }
    
    return response.json();
};

// Get trade by ID
export const getTradeById = async (tradeId) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/trades/${tradeId}`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch trade');
    }
    
    return response.json();
};

// Create new trade
export const createTrade = async (tradeData) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/trades`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(tradeData)
    });
    
    if (!response.ok) {
        throw new Error('Failed to create trade');
    }
    
    return response.json();
};

// Update trade
export const updateTrade = async (tradeId, tradeData) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/trades/${tradeId}`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(tradeData)
    });
    
    if (!response.ok) {
        throw new Error('Failed to update trade');
    }
    
    return response.json();
};

// Delete trade
export const deleteTrade = async (tradeId) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/trades/${tradeId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete trade');
    }
    
    return response.json();
};

// Get all orders
export const getOrders = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/orders`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch orders');
    }
    
    return response.json();
};

// Create new order
export const createOrder = async (orderData) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/trade/orders`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(orderData)
    });
    
    if (!response.ok) {
        throw new Error('Failed to create order');
    }
    
    return response.json();
};

// Get notifications
export const getNotifications = async () => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/notifications`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to fetch notifications');
    }
    
    return response.json();
};

// Mark notification as read
export const markNotificationRead = async (notificationId) => {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/notifications/${notificationId}/read`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    if (!response.ok) {
        throw new Error('Failed to mark notification as read');
    }
    
    return response.json();
};

// Refresh Access Token
export const refreshAccessToken = async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh?refresh_token=${refreshToken}`);
        if (response.ok) {
            const data = await response.json();
            storeTokens(data.access_token, data.refresh_token);
            return true;
        }
    } catch (error) {
        console.error('Token refresh failed:', error);
    }
    
    clearTokens();
    return false;
};

// Logout
export const logout = async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
        try {
            await fetch(`${API_BASE_URL}/auth/logout?refresh_token=${refreshToken}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    clearTokens();
};

// ==================== API CREDENTIALS MANAGEMENT ====================

// First-time API setup
export const setupAPICredentials = async (apiData) => {
    const response = await apiCall('/auth/first-time-api-setup', {
        method: 'POST',
        body: JSON.stringify(apiData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to set up API credentials');
};

// Update API credentials
export const updateAPICredentials = async (apiData) => {
    const response = await apiCall('/auth/update-api-credentials', {
        method: 'POST',
        body: JSON.stringify(apiData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to update API credentials');
};

// Check API setup status
export const checkAPISetup = async () => {
    const response = await apiCall('/auth/check-api-setup', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to check API setup status');
};

// Get API credentials info
export const getAPICredentialsInfo = async () => {
    const response = await apiCall('/auth/api-credentials-info', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to get API credentials info');
};

// ==================== DASHBOARD ENDPOINTS ====================

// Get Dashboard Data
export const getDashboardData = async () => {
    const response = await apiCall('/dashboard/dashboard', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch dashboard data');
};

// ==================== ZERODHA INTEGRATION ====================

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

// Activate Brokerage (Updated for proper Zerodha flow)
export const activateBrokerage = async (brokerageData) => {
    const response = await apiCall('/dashboard/activate-brokerage', {
        method: 'POST',
        body: JSON.stringify(brokerageData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to activate brokerage');
};

// ==================== TRADE ENDPOINTS ====================

// Get all trades
export const getTrades = async () => {
    const response = await apiCall('/trade/trades', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch trades');
};

// Create trade
export const createTrade = async (tradeData) => {
    const response = await apiCall('/trade/trade', {
        method: 'POST',
        body: JSON.stringify(tradeData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to create trade');
};

// Get specific trade
export const getTrade = async (tradeId) => {
    const response = await apiCall(`/trade/trade/${tradeId}`, {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch trade');
};

// Update trade
export const updateTrade = async (tradeId, tradeData) => {
    const response = await apiCall(`/trade/trade/${tradeId}`, {
        method: 'PUT',
        body: JSON.stringify(tradeData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to update trade');
};

// ==================== ORDER ENDPOINTS ====================

// Place buy order
export const placeBuyOrder = async (orderData) => {
    const response = await apiCall('/dashboard/order/buy', {
        method: 'POST',
        body: JSON.stringify(orderData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to place buy order');
};

// Place sell order
export const placeSellOrder = async (orderData) => {
    const response = await apiCall('/dashboard/order/sell', {
        method: 'POST',
        body: JSON.stringify(orderData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to place sell order');
};

// ==================== WATCHLIST ENDPOINTS ====================

// Get user's watchlist
export const getWatchlist = async () => {
    const response = await apiCall('/watchlist', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch watchlist');
};

// Add stock to watchlist
export const addToWatchlist = async (stockData) => {
    const response = await apiCall('/watchlist', {
        method: 'POST',
        body: JSON.stringify(stockData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to add stock to watchlist');
};

// Remove stock from watchlist
export const removeFromWatchlist = async (stockSymbol) => {
    const response = await apiCall(`/watchlist/${stockSymbol}`, {
        method: 'DELETE'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to remove stock from watchlist');
};

// Search stocks for watchlist
export const searchStocks = async (query) => {
    const response = await apiCall(`/watchlist/search?q=${encodeURIComponent(query)}`, {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to search stocks');
};

// Get real-time prices for watchlist stocks
export const getWatchlistPrices = async () => {
    const response = await apiCall('/watchlist/prices', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch watchlist prices');
};

// ==================== PORTFOLIO ENDPOINTS ====================

// Get portfolio holdings
export const getPortfolio = async () => {
    const response = await apiCall('/portfolio', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch portfolio');
};

// Get portfolio snapshot
export const getPortfolioSnapshot = async () => {
    const response = await apiCall('/portfolio/snapshot', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch portfolio snapshot');
};

// ==================== MARKET DATA ENDPOINTS ====================

// Get market data for specific stocks
export const getMarketData = async (symbols) => {
    const symbolsParam = Array.isArray(symbols) ? symbols.join(',') : symbols;
    const response = await apiCall(`/market/data?symbols=${encodeURIComponent(symbolsParam)}`, {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch market data');
};

// Get popular stocks
export const getPopularStocks = async () => {
    const response = await apiCall('/market/popular', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch popular stocks');
};

// ==================== TRADER DASHBOARD ENDPOINTS ====================

// Get trader dashboard data
export const getTraderDashboard = async () => {
    const response = await apiCall('/trader/dashboard', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch trader dashboard');
};

// Get trader clients
export const getTraderClients = async () => {
    const response = await apiCall('/trader/clients', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch trader clients');
};

// Add trader client
export const addTraderClient = async (clientData) => {
    const response = await apiCall('/trader/clients', {
        method: 'POST',
        body: JSON.stringify(clientData)
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to add trader client');
};

// ==================== NOTIFICATIONS ENDPOINTS ====================

// Get notifications
export const getNotifications = async () => {
    const response = await apiCall('/notifications', {
        method: 'GET'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to fetch notifications');
};

// Mark notification as read
export const markNotificationRead = async (notificationId) => {
    const response = await apiCall(`/notifications/${notificationId}/read`, {
        method: 'PUT'
    });
    
    if (response.ok) {
        return await response.json();
    }
    throw new Error('Failed to mark notification as read');
};

// ==================== UTILITY FUNCTIONS ====================

// Check if user is authenticated
export const isAuthenticated = () => {
    return !!getAuthToken();
};

// Get current user info from token
export const getCurrentUser = () => {
    const token = getAuthToken();
    if (!token) return null;
    
    try {
        // Decode JWT token (basic implementation)
        const payload = JSON.parse(atob(token.split('.')[1]));
        return {
            email: payload.sub,
            exp: payload.exp
        };
    } catch (error) {
        console.error('Error decoding token:', error);
        return null;
    }
};

// ==================== ZERODHA FLOW HELPER FUNCTIONS ====================

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

// ==================== USAGE EXAMPLES ====================

/*
// Example usage in your frontend components:

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

// Get Dashboard Data (now with real Zerodha data)
try {
    const dashboardData = await getDashboardData();
    console.log('Dashboard data:', dashboardData);
    // Update UI with dashboard data
} catch (error) {
    console.error('Failed to fetch dashboard:', error);
    // Show error message to user
}

// Logout
await logout();
// Redirect to login page
*/