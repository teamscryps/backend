import { z } from 'zod';

const API_BASE_URL = 'http://localhost:8000/api/v1';

// For development, use 'test' token if no token is provided
let authToken = localStorage.getItem('authToken') || 'test'; // Default for debug mode
let currentUser = JSON.parse(localStorage.getItem('currentUser')) || null;

// Function to set auth token (call this after login)
export const setAuthToken = (token) => {
  authToken = token;
  localStorage.setItem('authToken', token);
};

// Function to set current user info
export const setCurrentUser = (user) => {
  currentUser = user;
  localStorage.setItem('currentUser', JSON.stringify(user));
};

// Function to clear auth data (logout)
export const clearAuth = () => {
  authToken = 'test';
  currentUser = null;
  localStorage.removeItem('authToken');
  localStorage.removeItem('currentUser');
};

// Function to check if user is logged in
export const isLoggedIn = () => {
  return authToken && authToken !== 'test';
};

// Function to check if user has trader role
export const isTrader = () => {
  return currentUser && currentUser.role === 'trader';
};

// Function to get current user info
export const getCurrentUser = () => {
  return currentUser;
};

// Initialize authentication state on module load
export const initializeAuth = async () => {
  if (isLoggedIn()) {
    try {
      // Try to get fresh user info
      const userInfo = await getUserProfile();
      setCurrentUser(userInfo);
    } catch (error) {
      // Profile fetch failed, but token might still be valid
      // Set a default user instead of clearing auth
      console.warn('Failed to load user profile on init, using default user');
      setCurrentUser({
        id: 0,
        email: 'user@example.com',
        name: null,
        mobile: null,
        role: 'trader',
        broker: null,
        capital: 0,
        cash_available: 0,
        cash_blocked: 0,
        api_credentials_set: null,
        created_at: null,
        session_updated_at: null
      });
    }
  }
};

// Auto-initialize on import
if (typeof window !== 'undefined') {
  // Only run in browser environment
  initializeAuth();
}

// Zod Schemas for data validation

const TradeSchema = z.object({
  id: z.number(),
  stock: z.string(),
  name: z.string(),
  quantity: z.number(),
  buy_price: z.number(),
  current_price: z.number(),
  mtf_enabled: z.boolean(),
  timestamp: z.string(),
});

const TransactionSchema = z.object({
  id: z.number(),
  stock: z.string(),
  name: z.string(),
  quantity: z.number(),
  buy_price: z.number(),
  current_price: z.number(),
  mtf_enabled: z.boolean(),
  timestamp: z.string(),
  type: z.enum(['buy', 'sell']),
  pnl: z.number(),
  pnl_percent: z.number(),
});

const ClientSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
  pan: z.string(),
  phone: z.string(),
  status: z.enum(['active', 'pending', 'inactive']),
  portfolio_value: z.number(),
  join_date: z.string(),
  broker_api_key: z.string().nullish(),
});

const ClientDetailsSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
  pan: z.string(),
  phone: z.string(),
  status: z.enum(['active', 'pending', 'inactive']),
  portfolio_value: z.number(),
  allocated_funds: z.number(),
  remaining_funds: z.number(),
  total_pnl: z.number(),
  todays_pnl: z.number(),
  active_trades_count: z.number(),
  total_trades_count: z.number(),
  join_date: z.string(),
  broker_api_key: z.string().nullish(),
});

const OrderSchema = z.object({
  id: z.number(),
  client_id: z.number(),
  stock: z.string(),
  name: z.string(),
  quantity: z.number(),
  price: z.number(),
  type: z.enum(['buy', 'sell']),
  mtf_enabled: z.boolean(),
  status: z.enum(['pending', 'executed', 'cancelled']),
  timestamp: z.string(),
});

const StockOptionSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  price: z.number().nullable(),
  mtf_amount: z.number().nullable(),
});

const DashboardStatsSchema = z.object({
  totalPortfolio: z.number(),
  activeTrades: z.number(),
  todaysPNL: z.number(),
  activeClients: z.number(),
});

const WatchlistStockSchema = z.object({
    id: z.number(),
    symbol: z.string(),
    name: z.string(),
    currentPrice: z.number().nullable(),
    previousClose: z.number().nullable(),
    change: z.number().nullable(),
    changePercent: z.number().nullable(),
    high: z.number().nullable(),
    low: z.number().nullable(),
    volume: z.string().nullable()
});

const AddClientRequestSchema = z.object({
  name: z.string(),
  email: z.string(),
  pan: z.string(),
  phone: z.string(),
  broker_api_key: z.string().nullish(),
  status: z.enum(['active', 'pending', 'inactive']).nullish(),
});

const PlaceOrderRequestSchema = z.object({
  client_id: z.number(),
  stock: z.string(),
  quantity: z.number(),
  price: z.number(),
  type: z.enum(['buy', 'sell']),
  mtf_enabled: z.boolean(),
});

const TradesHistoryFilterSchema = z.enum(['today', 'last7days', 'thisMonth', 'profitable', 'loss']);

// Login/Auth Schemas
const LoginRequestSchema = z.object({
  username: z.string().email(),
  password: z.string(),
});

const TokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  refresh_token: z.string(),
}).passthrough();

const UserInfoSchema = z.any();

// Authentication Functions
export const login = async (email, password) => {
  try {
    console.log('Attempting login for:', email);
    const response = await fetch(`${API_BASE_URL}/auth/signin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    });

    console.log('Login response status:', response.status);
    if (!response.ok) {
      const errorData = await response.json();
      console.error('Login failed with error:', errorData);
      throw new Error(errorData.detail || 'Login failed');
    }

    const tokenData = await response.json();
    console.log('Token data received:', tokenData);
    const validatedToken = TokenResponseSchema.parse(tokenData);

    // Set the auth token
    setAuthToken(validatedToken.access_token);

    // Get user info
    try {
      const userInfo = await getUserProfile();
      setCurrentUser(userInfo);
      console.log('User profile loaded:', userInfo);
    } catch (profileError) {
      console.warn('Failed to load user profile, but login succeeded:', profileError);
      // Set a default user with basic info from login
      setCurrentUser({
        id: 0,
        email: email,
        name: null,
        mobile: null,
        role: 'trader', // Default to trader role
        broker: null,
        capital: 0,
        cash_available: 0,
        cash_blocked: 0,
        api_credentials_set: null,
        created_at: null,
        session_updated_at: null
      });
    }

    return {
      token: validatedToken,
      user: getCurrentUser()
    };
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};

export const logout = () => {
  clearAuth();
};

export const getUserProfile = async () => {
  const response = await fetch(`${API_BASE_URL}/auth/profile`, {
    headers: {
      'Authorization': `Bearer ${authToken}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to get user profile');
  }

  const userData = await response.json();
  console.log('Profile response data:', userData);

  // Since we use z.any(), just return the data as-is
  return userData;
};

export const refreshToken = async () => {
  // This would need to be implemented if you want to handle token refresh
  // For now, we'll just return the current token
  return authToken;
};

// Helper function to check if user is authenticated and has trader role
export const requireTraderAuth = () => {
  if (!isLoggedIn()) {
    throw new Error('Authentication required. Please login first.');
  }

  if (!isTrader()) {
    throw new Error('Trader role required. This action requires trader privileges.');
  }
};

async function fetchFromAPI(endpoint, schema) {
  try {
    const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    if (response.status === 404) {
      // Endpoint doesn't exist, return empty data instead of throwing
      console.warn(`API endpoint ${endpoint} not found (404), returning empty data`);
      return schema.parse ? schema.parse([]) : [];
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch from ${endpoint}: ${response.status}`);
    }

    const data = await response.json();
    return schema.parse ? schema.parse(data) : data;
  } catch (error) {
    if (error.message.includes('404')) {
      // If it's a 404, return empty data
      console.warn(`API endpoint ${endpoint} not found, returning empty data`);
      return schema.parse ? schema.parse([]) : [];
    }
    throw error;
  }
}

async function postToAPI(endpoint, data, schema) {
  try {
    const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify(data),
    });

    if (response.status === 404) {
      console.warn(`API endpoint ${endpoint} not found (404), skipping POST request`);
      return null;
    }

    if (!response.ok) {
      throw new Error(`Failed to post to ${endpoint}: ${response.status}`);
    }

    const responseData = await response.json();
    return schema.parse ? schema.parse(responseData) : responseData;
  } catch (error) {
    if (error.message.includes('404')) {
      console.warn(`API endpoint ${endpoint} not found, skipping POST request`);
      return null;
    }
    throw error;
  }
}

async function putToAPI(endpoint, data, schema) {
  try {
    const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify(data),
    });

    if (response.status === 404) {
      console.warn(`API endpoint ${endpoint} not found (404), skipping PUT request`);
      return null;
    }

    if (!response.ok) {
      throw new Error(`Failed to put to ${endpoint}: ${response.status}`);
    }

    const responseData = await response.json();
    return schema.parse ? schema.parse(responseData) : responseData;
  } catch (error) {
    if (error.message.includes('404')) {
      console.warn(`API endpoint ${endpoint} not found, skipping PUT request`);
      return null;
    }
    throw error;
  }
}

async function deleteFromAPI(endpoint) {
  try {
    const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${authToken}`,
      },
    });

    if (response.status === 404) {
      console.warn(`API endpoint ${endpoint} not found (404), skipping DELETE request`);
      return;
    }

    if (!response.ok) {
      throw new Error(`Failed to delete from ${endpoint}: ${response.status}`);
    }
  } catch (error) {
    if (error.message.includes('404')) {
      console.warn(`API endpoint ${endpoint} not found, skipping DELETE request`);
      return;
    }
    throw error;
  }
}

export const api = {
  // Client Management APIs
  getClients: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/clients', z.array(ClientSchema));
  },
  getClientDetails: (id) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/clients/${id}`, ClientDetailsSchema);
  },
  addClient: (clientData) => {
    requireTraderAuth();
    return postToAPI('trader/clients', clientData, ClientSchema);
  },
  updateClient: (id, clientData) => {
    requireTraderAuth();
    return putToAPI(`trader/clients/${id}`, clientData, ClientSchema);
  },
  deleteClient: (id) => {
    requireTraderAuth();
    return deleteFromAPI(`trader/clients/${id}`);
  },

  // Client Transactions and Trades APIs
  getClientTransactions: (id) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/clients/${id}/transactions`, z.array(TransactionSchema));
  },
  getClientActiveTrades: (id) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/clients/${id}/trades/active`, z.array(TradeSchema));
  },
  getClientTradesHistory: (id, filter) => {
    requireTraderAuth();
    const query = filter ? `?filter=${filter}` : '';
    return fetchFromAPI(`trader/clients/${id}/trades/history${query}`, z.array(TransactionSchema));
  },

  // Order Management APIs
  placeOrder: (orderData) => {
    requireTraderAuth();
    return postToAPI('trader/orders', orderData, OrderSchema);
  },
  getClientOrders: (id) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/clients/${id}/orders`, z.array(OrderSchema));
  },
  cancelOrder: (orderId) => {
    requireTraderAuth();
    return postToAPI(`trader/orders/${orderId}/cancel`, {}, z.object({ order_id: z.number(), status: z.string(), released_amount: z.number().nullish() }));
  },

  // Stock and Market Data APIs
  getStockOptions: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/stocks/options', z.array(StockOptionSchema)).catch(() => []);
  },
  getStockDetails: (symbol) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/stocks/${symbol}`, StockOptionSchema);
  },

  // Dashboard and Analytics APIs
  getDashboardStats: () => {
    requireTraderAuth();
    return fetchFromAPI('dashboard/dashboard', z.any()).catch(() => ({
      totalPortfolio: 0,
      activeTrades: 0,
      todaysPNL: 0,
      activeClients: 0
    }));
  },

  // Watchlist APIs
  getWatchlist: () => {
    requireTraderAuth();
    return fetchFromAPI('watchlist', z.array(WatchlistStockSchema)).catch(() => []);
  },
  addStockToWatchlist: (stock) => {
    requireTraderAuth();
    return postToAPI('watchlist', stock, WatchlistStockSchema);
  },
  removeStockFromWatchlist: (id) => {
    requireTraderAuth();
    return deleteFromAPI(`watchlist/${id}`);
  },

  // Direct Trader Trading APIs (Trader can trade for themselves)
  placeTraderOrder: (orderData) => {
    requireTraderAuth();
    return postToAPI('trader/my-orders', orderData, OrderSchema);
  },
  getTraderOrders: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/my-orders', z.array(OrderSchema));
  },
  getTraderHoldings: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/holdings', z.array(z.object({
      symbol: z.string(),
      quantity: z.number(),
      avg_price: z.number(),
      last_updated: z.string().nullable()
    }))).catch(() => []);
  },
  getTraderPortfolio: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/portfolio', z.any());
  },

  // Bulk Trading APIs
  tradeForAllClients: (stock, allocation, orderType, price, type) => {
    requireTraderAuth();
    const payload = {
      stock_ticker: stock,
      allocation: allocation,
      order_type: orderType,
      price: price,
      type: type
    };
    return postToAPI('trader/bulk-trade-all', payload, z.object({
      task_id: z.string(),
      message: z.string(),
      total_clients: z.number(),
      estimated_execution_time: z.string()
    }));
  },
  getBulkTradeStatus: (taskId) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/bulk-trade-status/${taskId}`, z.object({
      task_id: z.string(),
      status: z.enum(['pending', 'processing', 'completed', 'failed']),
      progress: z.number(),
      results: z.array(z.object({
        user_id: z.number(),
        status: z.enum(['success', 'failed', 'skipped']),
        trade_id: z.number().nullish(),
        reason: z.string().nullish()
      })),
      created_at: z.string(),
      completed_at: z.string().nullish()
    }));
  },

  // Stock Search and Discovery APIs
  searchStocks: (query) => {
    requireTraderAuth();
    return fetchFromAPI(`watchlist/search?q=${encodeURIComponent(query)}`, z.object({
      results: z.array(z.object({
        symbol: z.string(),
        name: z.string(),
        currentPrice: z.number().nullable(),
        changePercent: z.number().nullable()
      }))
    }));
  },

  // Audit Trail APIs
  getAuditLogs: (filters) => {
    requireTraderAuth();
    const query = new URLSearchParams(filters).toString();
    return fetchFromAPI(`audit/logs?${query}`, z.array(z.object({
      id: z.number(),
      actor_user_id: z.number(),
      target_user_id: z.number(),
      action: z.string(),
      description: z.string(),
      details: z.any(),
      created_at: z.string()
    })));
  }
};