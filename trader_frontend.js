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
      // Token might be expired, clear auth
      console.warn('Token expired, clearing auth');
      clearAuth();
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
  broker_api_key: z.string().optional(),
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
  broker_api_key: z.string().optional(),
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

const WatchlistStockCreateSchema = z.object({
    symbol: z.string()
});

const WatchlistSearchResultSchema = z.object({
    symbol: z.string(),
    name: z.string(),
    currentPrice: z.number().nullable(),
    changePercent: z.number().nullable()
});

const BulkTradeRequestSchema = z.object({
    broker_type: z.string(),
    stock_symbol: z.string(),
    percent_quantity: z.number(),
    user_ids: z.array(z.number())
});

const BulkTradeResponseSchema = z.object({
    task_id: z.string(),
    status: z.string()
});

const AddClientRequestSchema = z.object({
  name: z.string(),
  email: z.string(),
  pan: z.string(),
  phone: z.string(),
  broker_api_key: z.string().optional(),
  status: z.enum(['active', 'pending', 'inactive']).optional(),
});

const PlaceOrderRequestSchema = z.object({
  client_id: z.number(),
  stock: z.string(),
  quantity: z.number(),
  price: z.number(),
  type: z.enum(['buy', 'sell']),
  mtf_enabled: z.boolean(),
});

const TraderOrderRequestSchema = z.object({
  stock_ticker: z.string(),
  quantity: z.number(),
  order_type: z.enum(['buy', 'sell']),
  type: z.enum(['eq', 'mtf']),
  price: z.number().optional(),
  brokerage_charge: z.number().optional(),
  mtf_charge: z.number().optional()
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
});

const UserInfoSchema = z.object({
  id: z.number(),
  email: z.string(),
  name: z.string().nullable(),
  mobile: z.string().nullable(),
  role: z.string().nullable(),
  broker: z.string().nullable(),
  capital: z.number(),
  cash_available: z.number().nullable(),
  cash_blocked: z.number().nullable(),
  api_credentials_set: z.boolean().nullable(),
  created_at: z.string().nullable(),
  session_updated_at: z.string().nullable(),
});

// Authentication Functions
export const login = async (email, password) => {
  try {
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

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Login failed');
    }

    const tokenData = await response.json();
    const validatedToken = TokenResponseSchema.parse(tokenData);

    // Set the auth token
    setAuthToken(validatedToken.access_token);

    // Get user info
    const userInfo = await getUserProfile();
    setCurrentUser(userInfo);

    return {
      token: validatedToken,
      user: userInfo
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
  return UserInfoSchema.parse(userData);
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
  const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
    headers: {
      'Authorization': `Bearer ${authToken}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch from ${endpoint}`);
  }
  const data = await response.json();
  return schema.parse(data);
}

async function postToAPI(endpoint, data, schema) {
  const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error(`Failed to post to ${endpoint}`);
  }
  const responseData = await response.json();
  return schema.parse(responseData);
}

async function putToAPI(endpoint, data, schema) {
  const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error(`Failed to put to ${endpoint}`);
  }
  const responseData = await response.json();
  return schema.parse(responseData);
}

async function deleteFromAPI(endpoint) {
  const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${authToken}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete from ${endpoint}`);
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
  placeOrder: (clientId, orderData) => {
    requireTraderAuth();
    return postToAPI(`trader/clients/${clientId}/orders`, orderData, z.object({
      order_id: z.number(),
      status: z.string(),
      message: z.string(),
      broker_order_id: z.string().optional()
    }));
  },
  getClientOrders: (id) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/clients/${id}/orders`, z.array(OrderSchema));
  },
  cancelOrder: (orderId) => {
    requireTraderAuth();
    return postToAPI(`trader/orders/${orderId}/cancel`, {}, z.object({
      order_id: z.number(),
      status: z.string(),
      released_amount: z.number().optional()
    }));
  },

  // Stock and Market Data APIs
  getStockOptions: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/stocks/options', z.array(StockOptionSchema));
  },
  getStockDetails: (symbol) => {
    requireTraderAuth();
    return fetchFromAPI(`trader/stocks/${symbol}`, StockOptionSchema);
  },

  // Dashboard and Analytics APIs
  getDashboardStats: () => {
    requireTraderAuth();
    return fetchFromAPI('dashboard/dashboard', z.any());
  },

  // Watchlist APIs
  getWatchlist: () => {
    requireTraderAuth();
    return fetchFromAPI('watchlist', z.array(WatchlistStockSchema));
  },
  addStockToWatchlist: (symbol) => {
    requireTraderAuth();
    return postToAPI('watchlist', { symbol }, WatchlistStockSchema);
  },
  removeStockFromWatchlist: (stockId) => {
    requireTraderAuth();
    return deleteFromAPI(`watchlist/${stockId}`);
  },
  searchStocks: (query) => {
    requireTraderAuth();
    return fetchFromAPI(`watchlist/search/${query}`, z.object({ results: z.array(WatchlistSearchResultSchema) }));
  },

  // Bulk Trading APIs - NEW FEATURE
  tradeForAllClients: async (stockSymbol, percentQuantity, orderType = 'buy', price = null, type = 'eq') => {
    requireTraderAuth();

    // Get all clients first
    const clients = await api.getClients();

    // Filter active clients only
    const activeClients = clients.filter(client => client.status === 'active');

    if (activeClients.length === 0) {
      throw new Error('No active clients found');
    }

    // Extract client IDs
    const clientIds = activeClients.map(client => client.id);

    // Prepare bulk trade request
    const bulkTradeRequest = {
      broker_type: 'zerodha', // Default broker, can be made configurable
      stock_symbol: stockSymbol,
      percent_quantity: percentQuantity,
      user_ids: clientIds
    };

    // Validate request
    BulkTradeRequestSchema.parse(bulkTradeRequest);

    // Execute bulk trade
    const response = await fetch(`${API_BASE_URL}/execution/bulk-execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify(bulkTradeRequest),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Bulk trade failed');
    }

    const result = await response.json();
    return BulkTradeResponseSchema.parse(result);
  },

  // Get bulk trade status
  getBulkTradeStatus: (taskId) => {
    requireTraderAuth();
    return fetchFromAPI(`execution/status/${taskId}`, z.object({
      task_id: z.string(),
      status: z.string(),
      results: z.array(z.object({
        user_id: z.number(),
        trade_id: z.number().optional(),
        status: z.string(),
        error: z.string().optional()
      })).optional()
    }));
  },

  // Direct Trader Trading APIs (Trader can trade for themselves)
  placeTraderOrder: (orderData) => {
    requireTraderAuth();
    return postToAPI('trader/my-orders', orderData, z.object({
      order_id: z.number(),
      status: z.string(),
      message: z.string(),
      broker_order_id: z.string().optional()
    }));
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
    })));
  },
  getTraderPortfolio: () => {
    requireTraderAuth();
    return fetchFromAPI('trader/portfolio', z.any());
  },
};

/*
USAGE EXAMPLES:

// 1. Login as trader
try {
  const result = await login('trader@example.com', 'password');
  console.log('Logged in as:', result.user.name);
  console.log('Role:', result.user.role); // Should be 'trader'
} catch (error) {
  console.error('Login failed:', error.message);
}

// 2. Check authentication status
if (isLoggedIn()) {
  console.log('User is logged in');
  if (isTrader()) {
    console.log('User has trader role');
  }
}

// 3. Get all clients
try {
  const clients = await api.getClients();
  console.log('Total clients:', clients.length);
  console.log('Active clients:', clients.filter(c => c.status === 'active').length);
} catch (error) {
  console.error('Failed to get clients:', error.message);
}

// 4. Trade for ALL clients at once - NEW FEATURE!
try {
  const bulkTradeResult = await api.tradeForAllClients(
    'RELIANCE',    // Stock symbol
    25.0,         // 25% of each client's capital
    'buy',        // 'buy' or 'sell'
    null,         // null for market order, price for limit order
    'eq'          // 'eq' for equity, 'mtf' for margin trading
  );

  console.log('Bulk trade started:', bulkTradeResult);
  console.log('Task ID:', bulkTradeResult.task_id);

  // Check status after some time
  setTimeout(async () => {
    try {
      const status = await api.getBulkTradeStatus(bulkTradeResult.task_id);
      console.log('Bulk trade status:', status);
    } catch (error) {
      console.error('Failed to get bulk trade status:', error.message);
    }
  }, 5000);

} catch (error) {
  console.error('Bulk trade failed:', error.message);
}

// 5. Individual client trading (existing functionality)
try {
  // Place order for specific client
  const orderResult = await api.placeOrder(1, {
    stock_ticker: 'TCS',
    quantity: 10,
    order_type: 'buy',
    type: 'eq',
    price: null // market order
  });
  console.log('Order placed for client 1:', orderResult);
} catch (error) {
  console.error('Individual order failed:', error.message);
}

// 6. Watchlist Management
try {
  // Get current watchlist
  const watchlist = await api.getWatchlist();
  console.log('Current watchlist:', watchlist);

  // Add a stock to watchlist
  const newStock = await api.addStockToWatchlist('RELIANCE');
  console.log('Added stock to watchlist:', newStock);

  // Search for stocks
  const searchResults = await api.searchStocks('reliance');
  console.log('Search results:', searchResults.results);

  // Remove a stock from watchlist
  await api.removeStockFromWatchlist(1);
  console.log('Stock removed from watchlist');
} catch (error) {
  console.error('Watchlist operation failed:', error.message);
}

// 7. Trader direct trading
try {
  // Place a buy order for yourself
  const buyOrder = await api.placeTraderOrder({
    stock_ticker: 'RELIANCE',
    quantity: 10,
    order_type: 'buy',
    type: 'eq',
    price: null // market order
  });
  console.log('Buy order placed:', buyOrder);

  // Get your orders
  const myOrders = await api.getTraderOrders();
  console.log('My orders:', myOrders);

  // Get your holdings
  const myHoldings = await api.getTraderHoldings();
  console.log('My holdings:', myHoldings);

  // Get portfolio summary
  const portfolio = await api.getTraderPortfolio();
  console.log('Portfolio summary:', portfolio);
} catch (error) {
  console.error('Trading failed:', error.message);
}
*/

export default api;
