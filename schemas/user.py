from pydantic import BaseModel

class UserBase(BaseModel):
    email:str
    password:str

class UserOut(BaseModel):
    id: str
    email: str

    class Config:
        orm_mode=True