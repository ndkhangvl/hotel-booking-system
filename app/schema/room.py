from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from decimal import Decimal
from datetime import date


class AmenityResponse(BaseModel):
    amenity_id: UUID
    name: str
    icon_url: Optional[str] = None

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    room_id: UUID
    branch_id: UUID
    room_type_id: Optional[UUID] = None
    room_type_name: Optional[str] = None
    room_number: str
    price: Decimal
    people_number: int
    created_date: Optional[date] = None
    del_flg: int
    amenities: List[AmenityResponse] = []

    class Config:
        from_attributes = True


class RoomListResponse(BaseModel):
    items: List[RoomResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RoomInitializeResponse(BaseModel):
    total_rooms: int
    available_rooms: int
    occupied_rooms: int


class RoomTypeResponse(BaseModel):
    room_type_id: UUID
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class RoomUpsertRequest(BaseModel):
    room_id: Optional[UUID] = None          # None => insert, có giá trị => update
    branch_id: UUID
    room_type_id: Optional[UUID] = None
    room_number: str
    price: Optional[Decimal] = None
    people_number: Optional[int] = 1
    del_flg: int = 0                        # 0: còn trống, 1: đã đặt, 2: đang sử dụng, 3: không sử dụng
    amenity_ids: List[UUID] = []
