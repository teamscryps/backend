# API Endpoints Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All endpoints require Bearer token authentication in the header:
```
Authorization: Bearer <access_token>
```

---

## 1. Authentication Endpoints

### 1.1 User Registration
**POST** `/auth/signup`

**Description**: Register a new user account

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "testpass123"
  }'
```

### 1.2 User Login
**POST** `/auth/signin`

**Description**: Login with email and password

**Request Body** (form-encoded):
```
username=user@example.com&password=securepassword123
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/signin" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword123"
```

### 1.3 Request OTP
**POST** `/auth/request-otp`

**Description**: Request OTP for email-based login

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response**:
```json
{
  "message": "OTP sent to email"
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/request-otp" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

### 1.4 OTP Login
**POST** `/auth/otp-login`

**Description**: Login using OTP

**Request Body**:
```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/otp-login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp": "123456"
  }'
```

### 1.5 Refresh Token
**POST** `/auth/refresh`

**Description**: Refresh access token using refresh token

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

### 1.6 Logout
**POST** `/auth/logout`

**Description**: Logout and invalidate refresh token

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response**:
```json
{
  "message": "Logged out successfully"
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

---

## 2. Dashboard Endpoints

### 2.1 Get Dashboard Data
**GET** `/dashboard/dashboard`

**Description**: Fetch all dashboard data including portfolio, trades, and funds

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response**:
```json
{
  "activity_status": {
    "is_active": true,
    "last_active": "Jul 30, 2025 05:29:45"
  },
  "portfolio_overview": {
    "value": 35000.0,
    "change_percentage": 0.0
  },
  "ongoing_trades": [
    {
      "stock": "TCS",
      "bought": 3500.0,
      "quantity": 10,
      "capital_used": 35000.0,
      "profit": 0
    }
  ],
  "recent_trades": [
    {
      "date": "Jul 28, 2025 11:50:05",
      "stock": "TCS",
      "bought": 3500.0,
      "sold": 0,
      "quantity": 10,
      "capital_used": 35000.0,
      "profit": 0
    }
  ],
  "overall_profit": {
    "value": 0,
    "percentage": 0.0,
    "last_7_days": [0, 0, 0, 0, 0, 0, 0]
  },
  "unused_funds": 2300,
  "allocated_funds": 0,
  "upcoming_trades": {
    "count": 0,
    "holding_period": "3 Days"
  }
}
```

**Test Case**:
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/dashboard" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 2.2 Activate Brokerage
**POST** `/dashboard/activate-brokerage`

**Description**: Activate a brokerage account (Zerodha or Groww)

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body** (Zerodha):
```json
{
  "brokerage": "zerodha",
  "api_url": "https://api.kite.trade",
  "api_key": "your_zerodha_api_key",
  "api_secret": "your_zerodha_api_secret",
  "request_token": "your_request_token"
}
```

**Request Body** (Groww):
```json
{
  "brokerage": "groww",
  "api_url": "https://api.groww.in",
  "api_key": "your_groww_api_key",
  "api_secret": "your_groww_api_secret"
}
```

**Response**:
```json
{
  "message": "zerodha activated successfully",
  "session_id": "encrypted_session_id"
}
```

**Test Case** (Zerodha):
```bash
curl -X POST "http://localhost:8000/api/v1/dashboard/activate-brokerage" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "brokerage": "zerodha",
    "api_url": "https://api.kite.trade",
    "api_key": "test_api_key",
    "api_secret": "test_api_secret",
    "request_token": "test_request_token"
  }'
```

**Test Case** (Groww):
```bash
curl -X POST "http://localhost:8000/api/v1/dashboard/activate-brokerage" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "brokerage": "groww",
    "api_url": "https://api.groww.in",
    "api_key": "test_api_key",
    "api_secret": "test_api_secret"
  }'
```

### 2.3 Get Specific Trade
**GET** `/dashboard/trade/{trade_id}`

**Description**: Fetch details of a specific trade by ID

**Headers**:
```
Authorization: Bearer <access_token>
```

**Path Parameters**:
- `trade_id` (integer): The ID of the trade to fetch

**Response**:
```json
{
  "id": 1,
  "order_id": 1,
  "stock_ticker": "AAPL",
  "buy_price": 150.0,
  "sell_price": 160.0,
  "quantity": 10,
  "capital_used": 1500.0,
  "order_executed_at": "2024-01-15T14:30:25",
  "status": "closed",
  "brokerage_charge": 10.0,
  "mtf_charge": 5.0,
  "type": "eq"
}
```

**Test Case**:
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/trade/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 2.4 Place Buy Order
**POST** `/dashboard/order/buy`

**Description**: Place a buy order with the specified brokerage

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "stock_ticker": "AAPL",
  "quantity": 10,
  "price": 150.0,
  "order_type": "buy"
}
```

**Response**:
```json
{
  "id": 1,
  "user_id": 1,
  "stock_symbol": "AAPL",
  "quantity": 10,
  "order_type": "buy",
  "price": 150.0,
  "mtf_enabled": false,
  "order_executed_at": "2024-01-15T14:30:25"
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/dashboard/order/buy" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "stock_ticker": "AAPL",
    "quantity": 10,
    "price": 150.0,
    "order_type": "buy"
  }'
```

### 2.5 Place Sell Order
**POST** `/dashboard/order/sell`

**Description**: Place a sell order with the specified brokerage

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "stock_ticker": "AAPL",
  "quantity": 10,
  "price": 160.0,
  "order_type": "sell"
}
```

**Response**:
```json
{
  "id": 2,
  "user_id": 1,
  "stock_symbol": "AAPL",
  "quantity": 10,
  "order_type": "sell",
  "price": 160.0,
  "mtf_enabled": false,
  "order_executed_at": "2024-01-15T14:30:25"
}
```

**Test Case**:
```bash
curl -X POST "http://localhost:8000/api/v1/dashboard/order/sell" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "stock_ticker": "AAPL",
    "quantity": 10,
    "price": 160.0,
    "order_type": "sell"
  }'
```

---

## 3. Error Responses

### 3.1 Authentication Errors
```json
{
  "detail": "Incorrect email or password"
}
```

```json
{
  "detail": "Invalid or expired OTP"
}
```

```json
{
  "detail": "Invalid refresh token"
}
```

### 3.2 Authorization Errors
```json
{
  "detail": "Not authenticated"
}
```

### 3.3 Validation Errors
```json
{
  "detail": "Invalid brokerage"
}
```

```json
{
  "detail": "Request token required for Zerodha"
}
```

### 3.4 Business Logic Errors
```json
{
  "detail": "Broker not activated"
}
```

```json
{
  "detail": "Trade not found"
}
```

```json
{
  "detail": "Failed to validate Zerodha credentials"
}
```

---

## 4. Rate Limiting

All endpoints have rate limiting applied:
- **Dashboard endpoints**: 3 requests per second
- **Trade endpoints**: 5 requests per second
- **Order endpoints**: 3 requests per second

When rate limit is exceeded:
```json
{
  "detail": "Too many requests"
}
```

---

## 5. Datetime Format

All datetime fields use the format: `"MMM DD, YYYY HH:MM:SS"`

**Examples**:
- `"Jul 30, 2025 05:29:45"`
- `"Jan 15, 2024 14:30:25"`

---

## 6. Complete Test Script

```bash
#!/bin/bash

# Base URL
BASE_URL="http://localhost:8000/api/v1"

# Test user registration
echo "Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "testpass123"
  }')

echo "Register response: $REGISTER_RESPONSE"

# Extract access token
TOKEN=$(echo $REGISTER_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "Access token: $TOKEN"

# Test dashboard data
echo "Testing dashboard data..."
curl -X GET "$BASE_URL/dashboard/dashboard" \
  -H "Authorization: Bearer $TOKEN"

# Test brokerage activation
echo "Testing brokerage activation..."
curl -X POST "$BASE_URL/dashboard/activate-brokerage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "brokerage": "groww",
    "api_url": "https://api.groww.in",
    "api_key": "test_api_key",
    "api_secret": "test_api_secret"
  }'

# Test buy order
echo "Testing buy order..."
curl -X POST "$BASE_URL/dashboard/order/buy" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_ticker": "AAPL",
    "quantity": 10,
    "price": 150.0,
    "order_type": "buy"
  }'

echo "All tests completed!"
```

---

## 7. Environment Setup

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Redis server

### Installation
```bash
# Clone repository
git clone <repository-url>
cd backend

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
alembic upgrade head

# Start server
python main.py
```

### Environment Variables
Create a `.env` file:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379
```

---

## 8. API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` 