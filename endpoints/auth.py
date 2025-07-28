from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, Token, OTPCreate, OTPLogin
from security import create_access_token, create_refresh_token, verify_password, verify_refresh_token, verify_otp
from auth_service import create_user, get_user_by_email, update_refresh_token, generate_and_store_otp, verify_user_otp, invalidate_refresh_token

router = APIRouter()

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