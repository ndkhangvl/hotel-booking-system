from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional
from datetime import date, time

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str # 'Guest', 'Customer', 'Receptionist', 'Admin'

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    user_id: UUID4
    created_date: Optional[date]
    created_time: Optional[time]
    del_flg: int

    class Config:
        from_attributes = True