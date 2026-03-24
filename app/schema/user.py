from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, time
from uuid import UUID 

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str # 'Guest', 'Customer', 'Receptionist', 'Admin'

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    user_id: UUID 
    created_date: Optional[date]
    created_time: Optional[time]
    del_flg: int

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None

class UserPaginationResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int