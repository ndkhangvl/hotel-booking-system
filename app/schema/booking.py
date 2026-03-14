from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, time
from enum import Enum
from uuid import UUID # Dùng UUID thường để tránh lỗi 422 khắt khe của UUID4

class BookingStatus(str, Enum):
    PENDING = 'Pending'
    CONFIRMED = 'Confirmed'
    CHECKED_IN = 'Checked-in'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'

class BookingBase(BaseModel):
    user_id: UUID
    room_id: UUID
    voucher_code: Optional[str] = None
    from_date: date
    to_date: date

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    booking_id: UUID
    total_price: float
    status: BookingStatus
    
    # Các trường Audit tự sinh từ DB
    created_date: Optional[date]
    created_time: Optional[time]
    created_user: Optional[UUID]
    updated_date: Optional[date]
    updated_time: Optional[time]
    updated_user: Optional[UUID]
    del_flg: int = 0

    class Config:
        from_attributes = True

class BookingAdminUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    room_id: Optional[UUID] = None
    voucher_code: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    total_price: Optional[float] = Field(None, ge=0)
    del_flg: Optional[int] = None