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

// ==================== AUTHENTICATION ENDPOINTS ====================

// User Registration
export const signup = async (email, password) => {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password })
    });
    
    if (response.ok) {
        const data = await response.json();
        storeTokens(data.access_token, data.refresh_token);
        return data;
    }
    throw new Error('Signup failed');
};

// User Login
export const signin = async (email, password) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await fetch(`${API_BASE_URL}/auth/signin`, {
        method: 'POST',
        body: formData
    });
    
    if (response.ok) {
        const data = await response.json();
        storeTokens(data.access_token, data.refresh_token);
        return data;
    }
    throw new Error('Login failed');
};

// OTP Request
export const requestOTP = async (email) => {
    const response = await fetch(`${API_BASE_URL}/auth/request-otp`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email })
    });
    
    if (!response.ok) {
        throw new Error('OTP request failed');
    }
    return await response.json();
};

// OTP Login
export const otpLogin = async (email, otp) => {
    const response = await fetch(`${API_BASE_URL}/auth/otp-login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, otp })
    });
    
    if (response.ok) {
        const data = await response.json();
        storeTokens(data.access_token, data.refresh_token);
        return data;
    }
    throw new Error('OTP login failed');
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

// Activate Brokerage
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

// ==================== USAGE EXAMPLES ====================

/*
// Example usage in your frontend components:

// Login
try {
    const userData = await signin('user@example.com', 'password');
    console.log('Logged in:', userData);
    // Redirect to dashboard or update UI
} catch (error) {
    console.error('Login failed:', error);
    // Show error message to user
}

// Get Dashboard Data
try {
    const dashboardData = await getDashboardData();
    console.log('Dashboard data:', dashboardData);
    // Update UI with dashboard data
} catch (error) {
    console.error('Failed to fetch dashboard:', error);
    // Show error message to user
}

// Activate Brokerage
try {
    const brokerageData = {
        brokerage: 'zerodha',
        api_url: 'https://api.kite.trade',
        api_key: 'your_api_key',
        api_secret: 'your_api_secret',
        request_token: 'your_request_token'
    };
    const result = await activateBrokerage(brokerageData);
    console.log('Brokerage activated:', result);
    // Update UI
} catch (error) {
    console.error('Brokerage activation failed:', error);
    // Show error message to user
}

// Logout
await logout();
// Redirect to login page
*/ 