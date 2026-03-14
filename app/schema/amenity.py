from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import date, time
from uuid import UUID

class AmenityBase(BaseModel):
    name: str = Field(..., max_length=100)
    # icon_url có thể để str hoặc HttpUrl nếu bạn muốn validate chặt chẽ
    icon_url: Optional[str] = Field(None, max_length=255)

class AmenityCreate(AmenityBase):
    created_user: Optional[UUID] = None

class AmenityUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    icon_url: Optional[str] = Field(None, max_length=255)
    updated_user: Optional[UUID] = None
    del_flg: Optional[int] = None

class AmenityResponse(AmenityBase):
    amenity_id: UUID
    created_date: Optional[date]
    created_time: Optional[time]
    created_user: Optional[UUID]
    updated_date: Optional[date]
    updated_time: Optional[time]
    updated_user: Optional[UUID]
    del_flg: int

    class Config:
        from_attributes = True