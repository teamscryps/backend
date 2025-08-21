
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserRegistration(UserBase):
    # For registration without password - system will generate one
    mobile: str  # Mobile number is now required

class User(UserBase):
    id: int
    capital: int
    name: str | None
    mobile: str | None
    broker: str | None
    created_at: datetime | None
    session_updated_at: datetime | None
    api_credentials_set: bool | None
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class OTPCreate(BaseModel):
    email: EmailStr

class OTPLogin(BaseModel):
    email: EmailStr
    otp: str

class FirstTimeAPISetup(BaseModel):
    api_key: str
    api_secret: str
    broker: str
    request_token: str | None = None  # For Zerodha
    totp_secret: str | None = None  # For Groww
    auth_code: str | None = None  # For Upstox

class ZerodhaDailyLogin(BaseModel):
    request_token: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


class UpdateName(BaseModel):
    name: str
    mobile: str | None = None
