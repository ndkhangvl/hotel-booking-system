from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CustomerSchema(BaseModel):
    user_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class BookingInfoSchema(BaseModel):
    booking_code: str
    room_type_name: str
    room_number: str
    check_in_date: datetime
    check_out_date: datetime
    total_nights: int
    traveler_type: Optional[str] = None

class RatingSchema(BaseModel):
    overall: int
    cleanliness: int
    service: int
    location: int

class HotelReplySchema(BaseModel):
    replied_by_user_id: str
    replied_by_name: str
    content: str
    replied_at: datetime

class ReviewCreate(BaseModel):
    branch_code: str
    booking_id: str
    room_id: str
    customer: CustomerSchema
    booking_info: BookingInfoSchema
    rating: RatingSchema
    comment: str
    attached_images: Optional[List[str]] = []

class ReviewResponse(ReviewCreate):
    id: str = Field(alias="_id")
    hotel_reply: Optional[HotelReplySchema] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
