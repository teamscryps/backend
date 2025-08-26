from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, jwt
from config import settings
from database import get_db
from sqlalchemy.orm import Session
import random
import string

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/signin")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_refresh_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))

def verify_otp(otp: str, stored_otp: str, expiry: datetime) -> bool:
    if not stored_otp or not expiry:
        return False
    if datetime.utcnow() > expiry:
        return False
    return otp == stored_otp

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Test shortcut: allow header token 'test' to map to first user (ONLY when DEBUG)
    if settings.DEBUG and token == 'test':
        from models.user import User
        # Prefer trader role for debug operations requiring elevated rights
        trader = db.query(User).filter(User.role=='trader').first()
        if trader:
            return trader
        user = db.query(User).first()
        if user:
            return user
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    from models.user import User
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user 