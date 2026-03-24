from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time
from enum import Enum
from uuid import UUID # Dùng UUID thường để tránh lỗi 422 khắt khe của UUID4

class BookingStatus(str, Enum):
    PENDING = 'Pending'
    CONFIRMED = 'Confirmed'
    CHECKED_IN = 'Checked-in'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'


class PaymentStatus(str, Enum):
    UNPAID = 'unpaid'
    PAID = 'paid'

class BookingBase(BaseModel):
    user_id: Optional[UUID] = None
    branch_code: Optional[str] = None
    branch_room_id: Optional[UUID] = None
    room_id: Optional[UUID] = None
    voucher_code: Optional[str] = Field(None, max_length=20)
    customer_name: str = Field(..., max_length=100)
    customer_email: str = Field(..., max_length=150)
    customer_phonenumber: str = Field(..., max_length=15)
    note: Optional[str] = None
    from_date: date
    to_date: date

class BookingCreate(BookingBase):
    total_price: Optional[float] = Field(None, ge=0)


class BookingAdminCreate(BookingBase):
    total_price: Optional[float] = Field(None, ge=0)
    status: BookingStatus = BookingStatus.PENDING
    payment_status: PaymentStatus = PaymentStatus.UNPAID

class BookingResponse(BookingBase):
    booking_id: UUID
    booking_code: Optional[str] = None
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


class BookingAdminResponse(BookingResponse):
    branch_name: Optional[str] = None
    room_type_name: Optional[str] = None
    room_number: Optional[str] = None
    payment_status: PaymentStatus = PaymentStatus.UNPAID

class BookingAdminPaginationResponse(BaseModel):
    items: List[BookingAdminResponse]
    total: int
    page: int
    page_size: int

class BookingAdminUpdate(BaseModel):
    user_id: Optional[UUID] = None
    branch_code: Optional[str] = None
    branch_room_id: Optional[UUID] = None
    room_id: Optional[UUID] = None
    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None
    voucher_code: Optional[str] = None
    customer_name: Optional[str] = Field(None, max_length=100)
    customer_email: Optional[str] = Field(None, max_length=150)
    customer_phonenumber: Optional[str] = Field(None, max_length=15)
    note: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    total_price: Optional[float] = Field(None, ge=0)
    del_flg: Optional[int] = None