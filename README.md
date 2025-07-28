# FastAPI Backend Application

A comprehensive FastAPI backend application with authentication, user management, trading functionality, and database integration. This application provides a robust API for user authentication, order management, trade tracking, and audit logging.

##  Features

### Authentication & Security
- **JWT-based authentication** with access and refresh tokens
- **Password-based login** with bcrypt hashing
- **OTP-based login** with email delivery
- **Token refresh** mechanism
- **Secure logout** with token invalidation
- **Email verification** via SMTP

### Database & Models
- **PostgreSQL** database integration
- **SQLAlchemy ORM** for database operations
- **Alembic** for database migrations
- **User management** with extended profile fields
- **Order tracking** system
- **Trade management** functionality
- **Audit logging** for compliance

### API Structure
- **RESTful API** design
- **Organized endpoints** in dedicated folders
- **Pydantic schemas** for request/response validation
- **Comprehensive error handling**
- **Swagger/OpenAPI documentation**

##  Project Structure

```
backend/
├── main.py              # FastAPI application entrypoint
├── config.py            # Application settings and configuration
├── security.py          # Authentication and security utilities
├── auth_service.py      # Authentication service logic
├── routers.py           # API router configuration
├── database.py          # Database connection and session management
├── endpoints/           # API endpoints
│   ├── __init__.py
│   └── auth.py         # Authentication endpoints
├── models/              # SQLAlchemy database models
│   ├── __init__.py
│   ├── user.py         # User model with extended fields
│   ├── order.py        # Order management model
│   ├── trade.py        # Trade tracking model
│   └── audit.py        # Audit logging model
├── schemas/             # Pydantic schemas for API
│   ├── __init__.py
│   ├── user.py         # User-related schemas
│   ├── order.py        # Order-related schemas
│   └── trades.py       # Trade-related schemas
├── alembic/             # Database migrations
├── tests/               # Test files
├── requirements.txt     # Python dependencies
└── README.md           # This documentation
```

##  Setup & Installation

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Virtual environment (recommended)

### 1. Clone and Setup
```bash
# Navigate to the project directory
cd backend

# Create and activate virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Configuration
```bash
# Update database connection in database.py
DATABASE_URL = "postgresql://username:password@localhost:5432/database_name"

# Run database migrations
alembic upgrade head
```

### 3. Environment Variables
Create a `.env` file in the project root:
```env
# Database
DATABASE_URL=postgresql://postgres:1234@localhost:5432/scryps_db

# JWT Settings
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email Settings (for OTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# OTP Settings
OTP_EXPIRE_MINUTES=5
```

### 4. Run the Application
```bash
# Start the development server
uvicorn main:app --reload

# The API will be available at:
# http://127.0.0.1:8000
```

##  API Documentation

### Authentication Endpoints

#### User Registration
```http
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

#### Password-based Login
```http
POST /api/v1/auth/signin
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword
```

#### Request OTP
```http
POST /api/v1/auth/request-otp
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### OTP-based Login
```http
POST /api/v1/auth/otp-login
Content-Type: application/json

{
  "email": "user@example.com",
  "otp": "123456"
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

#### Logout
```http
POST /api/v1/auth/logout
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

### Response Format
All authentication endpoints return tokens in this format:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

##  Security Features

### JWT Authentication
- **Access tokens**: Short-lived (30 minutes) for API access
- **Refresh tokens**: Long-lived (7 days) for token renewal
- **Secure storage**: Tokens stored in database with user association
- **Token invalidation**: Logout removes refresh tokens

### Password Security
- **bcrypt hashing**: Secure password storage
- **Salt generation**: Automatic salt generation for each password
- **Verification**: Secure password comparison

### OTP Security
- **Time-based expiration**: OTP expires after 5 minutes
- **Single-use**: OTP is invalidated after successful login
- **Email delivery**: Secure OTP delivery via SMTP

##  Database Models

### User Model
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    mobile = Column(String)
    api_key = Column(String)
    api_secret = Column(String)
    broker = Column(String)
    session_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    session_updated_at = Column(DateTime, default=datetime.utcnow)
    refresh_token = Column(String, nullable=True)
    otp = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
```

### Additional Models
- **Order**: Trading order management
- **Trade**: Trade execution tracking
- **Audit**: Compliance and audit logging

##  Testing

```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=.
```

##  API Documentation

Once the server is running, you can access:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**: `http://127.0.0.1:8000/openapi.json`

##  Deployment

### Development
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
# Using Gunicorn with Uvicorn workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

##  Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

##  License

This project is licensed under the MIT License.

##  Support

For support and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the logs for debugging information

---

**Built with FastAPI, SQLAlchemy, and PostgreSQL**
