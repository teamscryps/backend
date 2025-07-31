from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    capital: int
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
