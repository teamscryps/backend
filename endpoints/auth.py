from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, Token, OTPCreate, OTPLogin, UserRegistration, FirstTimeAPISetup, ChangePassword, ForgotPassword, ResetPassword, UpdateName
from security import create_access_token, create_refresh_token, verify_password, verify_refresh_token, verify_otp, get_current_user
from auth_service import create_user, get_user_by_email, update_refresh_token, generate_and_store_otp, verify_user_otp, invalidate_refresh_token, create_user_with_generated_password, mark_api_credentials_set, change_user_password, reset_user_password, send_password_reset_email
from config import settings
from datetime import datetime, timedelta
from models.user import User
from kiteconnect import KiteConnect
from datetime import timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, Token, OTPCreate, OTPLogin, UserRegistration, FirstTimeAPISetup, ChangePassword, ForgotPassword, ResetPassword, UpdateName
from security import create_access_token, create_refresh_token, verify_password, verify_refresh_token, verify_otp, get_current_user
from auth_service import create_user, get_user_by_email, update_refresh_token, generate_and_store_otp, verify_user_otp, invalidate_refresh_token, create_user_with_generated_password, mark_api_credentials_set, change_user_password, reset_user_password, send_password_reset_email
from config import settings
from datetime import datetime, timedelta
from models.user import User
from kiteconnect import KiteConnect

from auth_service import create_trader_user, replace_trader_user
from schemas.user import TraderCreate

router = APIRouter()

@router.delete("/api-credentials")
async def delete_api_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user's API credentials"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.api_key = None
    user.api_secret = None
    user.broker = None
    user.broker_refresh_token = None
    user.session_id = None
    user.api_credentials_set = False
    user.session_updated_at = None

    db.commit()
    db.refresh(user)

    return {"message": "API credentials deleted successfully"}

@router.post("/register", response_model=dict)
async def register(user: UserRegistration, db: Session = Depends(get_db)):
    """Register a new user with email and mobile - password will be generated and sent via email"""
    db_user = await get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate mobile number format (basic validation)
    if not user.mobile or len(user.mobile) < 10:
        raise HTTPException(status_code=400, detail="Valid mobile number is required")
    
    new_user = await create_user_with_generated_password(db, user)
    return {"message": "Registration successful. Please check your email for login credentials."}

@router.put("/update-name")
async def update_name(
    name_data: UpdateName,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's name and mobile number"""
    if not name_data.name or len(name_data.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters long")

    if name_data.mobile is not None:
        if len(name_data.mobile) < 10:
            raise HTTPException(status_code=400, detail="Valid mobile number is required")

    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.name = name_data.name.strip()
    if name_data.mobile is not None:
        user.mobile = name_data.mobile
    db.commit()
    db.refresh(user)

    return {"message": "Name and mobile updated successfully", "name": user.name, "mobile": user.mobile}

@router.post("/signup", response_model=Token)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = await get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = await create_user(db, user)
    access_token = create_access_token(data={"sub": new_user.email})
    refresh_token = create_refresh_token(data={"sub": new_user.email})
    await update_refresh_token(db, new_user.id, refresh_token)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/create-trader", response_model=Token)
async def create_trader(trader: TraderCreate, db: Session = Depends(get_db)):
    """Create a new trader user and automatically link all existing unlinked clients to them"""
    db_user = await get_user_by_email(db, trader.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_trader = await create_trader_user(
        db=db,
        email=trader.email,
        password=trader.password,
        name=trader.name,
        mobile=trader.mobile
    )
    
    access_token = create_access_token(data={"sub": new_trader.email})
    refresh_token = create_refresh_token(data={"sub": new_trader.email})
    await update_refresh_token(db, new_trader.id, refresh_token)
    
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/replace-trader", response_model=Token)
async def replace_trader(trader: TraderCreate, db: Session = Depends(get_db)):
    """Replace the existing trader with a new one and transfer all clients"""
    db_user = await get_user_by_email(db, trader.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_trader = await replace_trader_user(
        db=db,
        email=trader.email,
        password=trader.password,
        name=trader.name,
        mobile=trader.mobile
    )
    
    access_token = create_access_token(data={"sub": new_trader.email})
    refresh_token = create_refresh_token(data={"sub": new_trader.email})
    await update_refresh_token(db, new_trader.id, refresh_token)
    
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/signin", response_model=Token)
async def signin(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    await update_refresh_token(db, user.id, refresh_token)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/change-password")
async def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password after verifying old password"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await change_user_password(db, user.id, password_data.old_password, password_data.new_password)
    return {"message": "Password changed successfully"}

@router.post("/forgot-password")
async def forgot_password(forgot_data: ForgotPassword, db: Session = Depends(get_db)):
    """Send OTP for password reset"""
    user = await get_user_by_email(db, forgot_data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate and store OTP
    await generate_and_store_otp(db, user)
    
    # Send password reset email
    await send_password_reset_email(forgot_data.email, user.otp)
    
    return {"message": "Password reset OTP sent to your email"}

@router.post("/reset-password")
async def reset_password(reset_data: ResetPassword, db: Session = Depends(get_db)):
    """Reset password using OTP verification"""
    await reset_user_password(db, reset_data.email, reset_data.otp, reset_data.new_password)
    return {"message": "Password reset successfully"}

@router.post("/first-time-api-setup")
async def first_time_api_setup(
    api_setup: FirstTimeAPISetup,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """First-time API credential setup after login"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Always overwrite existing API credentials if present
    user.api_key = api_setup.api_key
    user.api_secret = api_setup.api_secret
    user.broker = api_setup.broker
    user.api_credentials_set = True
    
    # Store API credentials in plaintext
    plain_api_key = api_setup.api_key
    plain_api_secret = api_setup.api_secret
    
    # For Zerodha: Handle request_token if provided (daily login)
    if api_setup.broker == "zerodha" and api_setup.request_token:
        try:
            # Exchange request_token for access_token
            kite = KiteConnect(api_key=api_setup.api_key)
            session_data = kite.generate_session(
                request_token=api_setup.request_token,
                api_secret=api_setup.api_secret
            )
            
            # Store access_token as session_id (plaintext)
            user.session_id = session_data["access_token"]
            
            # Store refresh token if available
            if "refresh_token" in session_data:
                user.broker_refresh_token = session_data["refresh_token"]
            
            # Update session timestamp
            user.session_updated_at = datetime.utcnow()
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to validate Zerodha credentials: {str(e)}")
    
    # Update user with plaintext credentials
    user.api_key = plain_api_key
    user.api_secret = plain_api_secret
    user.broker = api_setup.broker
    user.api_credentials_set = True
    
    # For non-Zerodha brokers, handle other tokens
    if api_setup.broker != "zerodha":
        plain_refresh_token = None
        if api_setup.broker == "groww" and api_setup.totp_secret:
            plain_refresh_token = api_setup.totp_secret
        elif api_setup.broker == "upstox" and api_setup.auth_code:
            plain_refresh_token = api_setup.auth_code
        elif api_setup.broker == "icici" and api_setup.request_token:
            # For ICICI, request_token is actually the access token
            user.session_id = api_setup.request_token
            user.session_updated_at = datetime.utcnow()
        
        user.broker_refresh_token = plain_refresh_token
    
    db.commit()
    db.refresh(user)
    
    return {"message": f"{api_setup.broker} API credentials set successfully"}

@router.post("/zerodha/daily-login")
async def zerodha_daily_login(
    request_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Daily Zerodha login to get fresh access token"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.api_credentials_set or user.broker != "zerodha":
        raise HTTPException(status_code=400, detail="Zerodha API credentials not set up")
    
    try:
        # Exchange request_token for access_token
        kite = KiteConnect(api_key=user.api_key)
        session_data = kite.generate_session(
            request_token=request_token,
            api_secret=user.api_secret
        )
        
        # Store new access_token (plaintext)
        user.session_id = session_data["access_token"]
        
        # Store refresh token if available
        if "refresh_token" in session_data:
            user.broker_refresh_token = session_data["refresh_token"]
        
        # Update session timestamp
        user.session_updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(user)
        
        return {"message": "Zerodha daily login successful", "session_updated_at": user.session_updated_at}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to complete Zerodha daily login: {str(e)}")

@router.get("/zerodha/session-status")
async def get_zerodha_session_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if Zerodha session is valid for today"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.api_credentials_set or user.broker != "zerodha":
        return {"session_valid": False, "reason": "Zerodha not set up"}
    
    if not user.session_id:
        return {"session_valid": False, "reason": "No active session"}
    
    # Check if session was updated today (IST)
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))  # IST timezone
    today_ist = datetime.now(ist_tz).date()
    
    if user.session_updated_at:
        session_date_ist = user.session_updated_at.replace(tzinfo=timezone.utc).astimezone(ist_tz).date()
        if session_date_ist == today_ist:
            return {"session_valid": True, "session_updated_at": user.session_updated_at}
        else:
            return {"session_valid": False, "reason": "Session expired (daily login required)"}
    
    return {"session_valid": False, "reason": "No session timestamp"}

@router.get("/icici/session-status")
async def get_icici_session_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if ICICI session is valid for today"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.api_credentials_set or user.broker != "icici":
        return {"session_valid": False, "reason": "ICICI not set up"}
    
    if not user.session_id:
        return {"session_valid": False, "reason": "No active session"}
    
    # Check if session was updated today (IST)
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))  # IST timezone
    today_ist = datetime.now(ist_tz).date()
    
    if user.session_updated_at:
        session_date_ist = user.session_updated_at.replace(tzinfo=timezone.utc).astimezone(ist_tz).date()
        if session_date_ist == today_ist:
            return {"session_valid": True, "session_updated_at": user.session_updated_at}
        else:
            return {"session_valid": False, "reason": "Session expired (daily login required)"}
    
    return {"session_valid": False, "reason": "No session timestamp"}

@router.post("/update-api-credentials")
async def update_api_credentials(
    api_setup: FirstTimeAPISetup,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update existing API credentials"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Store API credentials in plaintext
    plain_api_key = api_setup.api_key
    plain_api_secret = api_setup.api_secret
    
    # Store additional broker-specific data
    plain_refresh_token = None
    if api_setup.broker == "zerodha" and api_setup.request_token:
        plain_refresh_token = api_setup.request_token
    elif api_setup.broker == "groww" and api_setup.totp_secret:
        plain_refresh_token = api_setup.totp_secret
    elif api_setup.broker == "upstox" and api_setup.auth_code:
        plain_refresh_token = api_setup.auth_code
    
    # Update user with new encrypted credentials
    user.api_key = plain_api_key
    user.api_secret = plain_api_secret
    user.broker = api_setup.broker
    user.broker_refresh_token = plain_refresh_token
    user.api_credentials_set = True
    user.session_updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {"message": f"{api_setup.broker} API credentials updated successfully"}

@router.get("/check-api-setup")
async def check_api_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if user has set up API credentials"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"api_credentials_set": user.api_credentials_set}

@router.get("/api-credentials-info")
async def get_api_credentials_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current API credentials information (without exposing actual values)"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.api_credentials_set:
        raise HTTPException(status_code=404, detail="API credentials not set")
    
    return {
        "broker": user.broker,
        "api_credentials_set": user.api_credentials_set,
        "session_updated_at": user.session_updated_at,
        "has_api_key": bool(user.api_key),
        "has_api_secret": bool(user.api_secret),
        "has_broker_token": bool(user.broker_refresh_token)
    }

@router.post("/request-otp")
async def request_otp(otp_data: OTPCreate, db: Session = Depends(get_db)):
    user = await get_user_by_email(db, otp_data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await generate_and_store_otp(db, user)
    return {"message": "OTP sent to email"}

@router.post("/otp-login", response_model=Token)
async def otp_login(otp_data: OTPLogin, db: Session = Depends(get_db)):
    user = await get_user_by_email(db, otp_data.email)
    if not user or not verify_otp(otp_data.otp, user.otp, user.otp_expiry):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    await verify_user_otp(db, user)  # Clear OTP after use
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    await update_refresh_token(db, user.id, refresh_token)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    email = verify_refresh_token(refresh_token)
    user = await get_user_by_email(db, email)
    if not user or user.refresh_token != refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token(data={"sub": user.email})
    new_refresh_token = create_refresh_token(data={"sub": user.email})
    await update_refresh_token(db, user.id, new_refresh_token)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": new_refresh_token}

@router.post("/logout")
async def logout(refresh_token: str, db: Session = Depends(get_db)):
    email = verify_refresh_token(refresh_token)
    user = await get_user_by_email(db, email)
    if not user or user.refresh_token != refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    await invalidate_refresh_token(db, user.id)
    return {"message": "Logged out successfully"} 

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's profile information"""
    user = await get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "mobile": user.mobile,
        "created_at": user.created_at,
        "api_credentials_set": user.api_credentials_set,
        "broker": user.broker,
        
    } 