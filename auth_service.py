from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import UserCreate, UserRegistration
from security import get_password_hash, generate_otp, verify_password, verify_otp
from config import settings
from datetime import datetime, timedelta
import aiosmtplib
from email.message import EmailMessage
import secrets
import string
import re

def extract_name_from_email(email: str) -> str:
    """Extract name from email address (part before @)"""
    # Get the part before @ symbol
    name_part = email.split('@')[0]
    
    # Replace common separators with spaces and capitalize
    name_part = re.sub(r'[._-]', ' ', name_part)
    
    # Capitalize each word
    name_part = ' '.join(word.capitalize() for word in name_part.split())
    
    return name_part

def generate_password():
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(12))

async def create_user_with_generated_password(db: Session, user: UserRegistration):
    # Generate a secure password
    generated_password = generate_password()
    hashed_password = get_password_hash(generated_password)
    
    # Extract name from email
    extracted_name = extract_name_from_email(user.email)
    
    # Create user with mobile number and extracted name
    db_user = User(
        email=user.email, 
        password=hashed_password,
        mobile=user.mobile,
        name=extracted_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Send password via email
    await send_password_email(user.email, generated_password)
    
    return db_user

async def send_password_email(email: str, password: str):
    """Send generated password to user's email"""
    message = EmailMessage()
    message.set_content(f"""
    Welcome to Stonx!
    
    Your account has been created successfully.
    Your login credentials are:
    
    Email: {email}
    Password: {password}
    
    Please login with these credentials and set up your API credentials for the first time.
    
    Best regards,
    Stonx Team
    """)
    message["Subject"] = "Welcome to Stonx - Your Login Credentials"
    message["From"] = settings.SMTP_USERNAME
    message["To"] = email
    
    try:
        smtp_client = aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        async with smtp_client:
            await smtp_client.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send password email: {str(e)}")

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

async def mark_api_credentials_set(db: Session, user_id: int):
    """Mark that user has set up their API credentials"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.api_credentials_set = True
        db.commit()
        db.refresh(user)

async def change_user_password(db: Session, user_id: int, old_password: str, new_password: str):
    """Change user password after verifying old password"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify old password
    if not verify_password(old_password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # Hash and update new password
    hashed_new_password = get_password_hash(new_password)
    user.password = hashed_new_password
    db.commit()
    db.refresh(user)
    
    return user

async def reset_user_password(db: Session, email: str, otp: str, new_password: str):
    """Reset user password using OTP verification"""
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify OTP
    if not verify_otp(otp, user.otp, user.otp_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Hash and update new password
    hashed_new_password = get_password_hash(new_password)
    user.password = hashed_new_password
    
    # Clear OTP after use
    user.otp = None
    user.otp_expiry = None
    
    db.commit()
    db.refresh(user)
    
    return user

async def send_password_reset_email(email: str, otp: str):
    """Send password reset OTP to user's email"""
    message = EmailMessage()
    message.set_content(f"""
    Password Reset Request
    
    You have requested to reset your password.
    Your OTP for password reset is: {otp}
    
    This OTP will expire in 10 minutes.
    If you didn't request this, please ignore this email.
    
    Best regards,
    Stonx Team
    """)
    message["Subject"] = "Password Reset - Stonx"
    message["From"] = settings.SMTP_USERNAME
    message["To"] = email
    
    try:
        smtp_client = aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True,
        )
        async with smtp_client:
            await smtp_client.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send password reset email: {str(e)}")

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