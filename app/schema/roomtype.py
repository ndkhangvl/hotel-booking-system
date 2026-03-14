from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, time
from uuid import UUID

class RoomTypeBase(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = None

class RoomTypeCreate(RoomTypeBase):
    created_user: Optional[UUID] = None

class RoomTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    updated_user: Optional[UUID] = None
    del_flg: Optional[int] = None

class RoomTypeResponse(RoomTypeBase):
    room_type_id: UUID
    created_date: Optional[date]
    created_time: Optional[time]
    created_user: Optional[UUID]
    updated_date: Optional[date]
    updated_time: Optional[time]
    updated_user: Optional[UUID]
    del_flg: int

    class Config:
        from_attributes = True