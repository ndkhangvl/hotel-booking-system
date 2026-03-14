from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time
from decimal import Decimal
from uuid import UUID

class RoomBase(BaseModel):
    branch_id: UUID
    room_type_id: UUID
    room_number: str = Field(..., max_length=20)
    price: Decimal
    people_number: int

class RoomCreate(RoomBase):
    # Thường khi tạo mới, ta có thể truyền user ID tạo
    created_user: Optional[UUID] = None

class RoomUpdate(BaseModel):
    # Các trường có thể cập nhật
    room_type_id: Optional[UUID] = None
    room_number: Optional[str] = None
    price: Optional[Decimal] = None
    people_number: Optional[int] = None
    updated_user: Optional[UUID] = None
    del_flg: Optional[int] = None

class RoomResponse(RoomBase):
    room_id: UUID
    created_date: Optional[date]
    created_time: Optional[time]
    created_user: Optional[UUID]
    updated_date: Optional[date]
    updated_time: Optional[time]
    updated_user: Optional[UUID]
    del_flg: int

    class Config:
        from_attributes = True

class RoomResponseWithTypeName(BaseModel):
    room_id: UUID
    room_number: str
    price: Decimal
    people_number: int
    room_type_name: str  # Lấy từ bảng room_types
    branch_id: UUID
    del_flg: int

    class Config:
        from_attributes = True

class BranchRoomsResponse(BaseModel):
    branch_id: UUID
    rooms: List[RoomResponseWithTypeName]