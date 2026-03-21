from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class RoomImageBase(BaseModel):
    branch_room_id: str = Field(..., min_length=1, max_length=100)
    room_id: str = Field(..., min_length=1, max_length=100)
    branch_code: str = Field(..., min_length=1, max_length=100)
    image_url: HttpUrl
    is_thumbnail: bool = False
    sort_order: int = Field(default=1, ge=1)


class RoomImageCreate(RoomImageBase):
    created_user: Optional[str] = None


class RoomImageUpdate(BaseModel):
    image_url: Optional[HttpUrl] = None
    is_thumbnail: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=1)
    updated_user: Optional[str] = None


class RoomImageResponse(BaseModel):
    id: str = Field(alias="_id")
    branch_room_id: str
    room_id: str
    branch_code: str
    image_url: str
    is_thumbnail: bool
    sort_order: int
    created_date: Optional[str] = None
    created_time: Optional[str] = None
    created_user: Optional[str] = None
    updated_date: Optional[str] = None
    updated_time: Optional[str] = None
    updated_user: Optional[str] = None
    del_flg: int

    class Config:
        populate_by_name = True


class RoomImageListResponse(BaseModel):
    items: List[RoomImageResponse]


class RoomImageDeleteResponse(BaseModel):
    success: bool
    message: str


class SetThumbnailRequest(BaseModel):
    updated_user: Optional[str] = None


class ReorderRoomImageRequest(BaseModel):
    sort_order: int = Field(..., ge=1)
    updated_user: Optional[str] = None