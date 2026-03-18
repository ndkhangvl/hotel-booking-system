from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import date
from app.schema.booking import BookingCreate, BookingResponse, BookingAdminUpdate
from app.crud import booking as crud_booking

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=BookingResponse)
async def create_new_booking(booking: BookingCreate):
    try:
        return crud_booking.create_booking(booking)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo booking: {e}")

@router.get("/", response_model=List[BookingResponse])
async def read_bookings():
    try:
        return crud_booking.get_all_bookings()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi lấy danh sách booking: {e}")

@router.get("/{booking_id}", response_model=BookingResponse)
async def read_booking(booking_id: str):
    booking = crud_booking.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Không tìm thấy booking")
    return booking

@router.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking(booking_id: str, booking_update: BookingAdminUpdate):
    try:
        updated_booking = crud_booking.update_booking_by_admin(booking_id, booking_update)
        if not updated_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để cập nhật")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi cập nhật booking: {e}")

@router.delete("/{booking_id}")
async def delete_booking(booking_id: str):
    try:
        deleted_booking = crud_booking.delete_booking(booking_id)
        if not deleted_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để xóa")
        return {"message": "Xóa booking thành công", "booking_id": booking_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xóa booking: {e}")
    
@router.patch("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking_api(booking_id: str):
    try:
        updated_booking = crud_booking.confirm_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Xác nhận. Đơn không ở trạng thái Pending.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xác nhận booking: {e}")

@router.patch("/{booking_id}/check-in", response_model=BookingResponse)
async def check_in_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_in(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-in. Đơn chưa được Confirmed.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-in: {e}")

@router.patch("/{booking_id}/check-out", response_model=BookingResponse)
async def check_out_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_out(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-out. Khách chưa Check-in.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-out: {e}")

@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking_api(booking_id: str):
    try:
        updated_booking = crud_booking.cancel_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Hủy. Đơn không tồn tại hoặc đã xử lý.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi hủy booking: {e}")