from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import UserCreate
from security import get_password_hash, generate_otp
from config import settings
from datetime import datetime, timedelta
import aiosmtplib
from email.message import EmailMessage

async def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

async def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

async def update_refresh_token(db: Session, user_id: int, refresh_token: str):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.refresh_token = refresh_token
        db.commit()
        db.refresh(user)

async def invalidate_refresh_token(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.refresh_token = None
        db.commit()
        db.refresh(user)

async def generate_and_store_otp(db: Session, user: User):
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    user.otp = otp
    user.otp_expiry = expiry
    db.commit()
    db.refresh(user)
    
    # Send OTP via email
    message = EmailMessage()
    message.set_content(f" OTP for Stonx is: {otp}")
    message["Subject"] = "Your OTP for Login"
    message["From"] = settings.SMTP_USERNAME
    message["To"] = user.email
    
    try:
        smtp_client = aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,  # Use STARTTLS instead of direct TLS
            start_tls=True,  # Enable STARTTLS for Gmail
        )
        async with smtp_client:
            await smtp_client.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")

async def verify_user_otp(db: Session, user: User):
    user.otp = None
    user.otp_expiry = None
    db.commit()
    db.refresh(user) 