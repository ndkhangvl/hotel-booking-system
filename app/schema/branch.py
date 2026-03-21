from pydantic import BaseModel, Field
from datetime import date, time
from uuid import UUID
from typing import List, Optional
from decimal import Decimal

class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=15)

class BranchCreate(BranchBase):
    created_user: Optional[UUID] = None

class BranchUpdate(BaseModel):
    branch_code: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    created_user: Optional[UUID] = None # <--- Phải có cái này!
    del_flg: int

class BranchResponse(BranchBase):
    branch_code: str
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


class BranchRoomTypePriceResponse(BaseModel):
    room_type_id: UUID
    name: str
    description: Optional[str] = None
    price: Decimal


class BranchRoomAmenityResponse(BaseModel):
    name: str
    icon_url: Optional[str] = None


class BranchRoomDetailResponse(BaseModel):
    room_id: UUID
    branch_code: str
    room_type_id: Optional[UUID] = None
    room_type_name: Optional[str] = None
    description: Optional[str] = None
    price: Decimal
    people_number: int
    del_flg: int
    room_amenities: List[BranchRoomAmenityResponse] = []


class BranchDetailResponse(BranchResponse):
    rooms: List[BranchRoomDetailResponse] = []