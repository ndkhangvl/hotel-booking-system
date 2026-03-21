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
    price: Decimal
    people_number: int
    created_date: Optional[date] = None
    del_flg: int
    available_rooms: int = 0
    booked_rooms: int = 0
    in_use_rooms: int = 0
    unavailable_rooms: int = 0
    amenities: List[AmenityResponse] = []

    class Config:
        from_attributes = True


class RoomListResponse(BaseModel):
    items: List[RoomResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BranchRoomResponse(BaseModel):
    branch_room_id: UUID
    branch_id: UUID
    room_id: UUID
    room_number: str
    room_type_id: Optional[UUID] = None
    room_type_name: Optional[str] = None
    del_flg: int
    occupancy_status: int = 0

    class Config:
        from_attributes = True


class BranchRoomListResponse(BaseModel):
    items: List[BranchRoomResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BranchRoomUpsertRequest(BaseModel):
    branch_room_id: Optional[UUID] = None
    branch_id: UUID
    room_id: UUID
    room_number: str
    del_flg: int = 0


class BranchRoomDeleteRequest(BaseModel):
    branch_room_id: UUID


class RoomInitializeResponse(BaseModel):
    total_rooms: int
    available_rooms: int
    booked_rooms: int
    in_use_rooms: int
    unavailable_rooms: int


class RoomTypeResponse(BaseModel):
    room_type_id: UUID
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class RoomUpsertRequest(BaseModel):
    room_id: Optional[UUID] = None
    branch_id: UUID
    room_type_id: Optional[UUID] = None
    price: Optional[Decimal] = None
    people_number: Optional[int] = 1
    del_flg: int = 0                        # 0: còn trống, 1: đã đặt, 2: đang sử dụng, 3: không sử dụng
    amenity_ids: List[UUID] = []
