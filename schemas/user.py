
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    mobile: str | None
    broker: str | None
    created_at: datetime | None
    session_updated_at: datetime | None
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
