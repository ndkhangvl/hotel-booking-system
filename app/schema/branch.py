from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, time
from uuid import UUID

class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=15)

class BranchCreate(BranchBase):
    created_user: Optional[UUID] = None

class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=15)
    updated_user: Optional[UUID] = None
    del_flg: Optional[int] = None

class BranchResponse(BranchBase):
    branch_id: UUID
    created_date: Optional[date]
    created_time: Optional[time]
    created_user: Optional[UUID]
    updated_date: Optional[date]
    updated_time: Optional[time]
    updated_user: Optional[UUID]
    del_flg: int

    class Config:
        from_attributes = True
