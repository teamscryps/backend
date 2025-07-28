# FastAPI Auth App

A FastAPI application with user sign-up, password-based sign-in, OTP-based login, refresh token, and logout functionality using JWT authentication.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env` (update `SMTP_USERNAME` and `SMTP_PASSWORD` for email sending).

3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Access the API:
   - Swagger UI: `http://localhost:8000/docs`
   - Root endpoint: `http://localhost:8000`

## Endpoints
- `POST /api/v1/auth/signup`: Register a new user (returns access and refresh tokens).
- `POST /api/v1/auth/signin`: Login with email and password (returns access and refresh tokens).
- `POST /api/v1/auth/request-otp`: Request an OTP for login (sent to email).
- `POST /api/v1/auth/otp-login`: Login with email and OTP (returns access and refresh tokens).
- `POST /api/v1/auth/refresh`: Refresh access token using a valid refresh token.
- `POST /api/v1/auth/logout`: Invalidate refresh token to log out.
