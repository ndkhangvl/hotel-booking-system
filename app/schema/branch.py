from pydantic import BaseModel, Field
from datetime import date, time
from uuid import UUID
from typing import List, Optional

class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=15)

class BranchCreate(BranchBase):
    created_user: Optional[UUID] = None

class BranchUpdate(BaseModel):
    branch_id: Optional[UUID] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    created_user: Optional[UUID] = None # <--- Phải có cái này!

class BranchResponse(BranchBase):
    branch_id: UUID
    created_date: Optional[date] = None
    created_time: Optional[time] = None
    created_user: Optional[UUID] = None
    updated_date: Optional[date] = None
    updated_time: Optional[time] = None
    updated_user: Optional[UUID] = None
    del_flg: int
    total_rooms: int = 0 

    class Config:
        from_attributes = True

# Model bao bọc phân trang
class BranchPaginationResponse(BaseModel):
    items: List[BranchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class BranchInitializeResponse(BaseModel):
    total_branches: int
    active_branches: int
    total_rooms: int