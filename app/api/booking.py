from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
from app.schema.booking import BookingCreate, BookingResponse, BookingAdminUpdate
from app.crud import booking as crud_booking
# Giả sử bạn có hàm gửi mail ở đây
# from app.utils.email import send_confirm_email 
# Giả sử bạn có hàm lấy email user ở đây
from app.crud import user as crud_user 

router = APIRouter(prefix="/bookings", tags=["Bookings"])
routerReceptionist = APIRouter(prefix="/Receptionist/bookings", tags=["receptionist - Bookings"])
routerAdmin = APIRouter(prefix="/Admin/bookings", tags=["Admin - Bookings"])

@router.post("/user/", response_model=BookingResponse)
async def create_new_booking(booking: BookingCreate):
    try:
        return crud_booking.create_booking(booking)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo booking: {e}")


@routerReceptionist.get("/", response_model=List[BookingResponse])
async def read_bookings_for_receptionist():
    try:
        return crud_booking.get_all_bookings()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi lấy danh sách booking: {e}")

@routerReceptionist.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking_api(booking_id: str, background_tasks: BackgroundTasks):
    try:
        updated_booking = crud_booking.confirm_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Xác nhận. Đơn không ở trạng thái Pending.")
        
        # LOGIC GỬI MAIL:
        # Lấy email của khách hàng dựa trên user_id trong booking
        customer = crud_user.get_user_by_id(updated_booking['user_id'])
        if customer and customer.get('email'):
            # Thêm việc gửi mail vào hàng đợi chạy ngầm
            background_tasks.add_task(send_confirm_email, customer['email'], updated_booking)
            
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xác nhận booking: {e}")

@routerReceptionist.patch("/{booking_id}/check-in", response_model=BookingResponse)
async def check_in_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_in(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-in. Đơn chưa được Confirmed.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-in: {e}")

@routerReceptionist.patch("/{booking_id}/check-out", response_model=BookingResponse)
async def check_out_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_out(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-out. Khách chưa Check-in.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-out: {e}")

@routerReceptionist.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking_api(booking_id: str):
    try:
        updated_booking = crud_booking.cancel_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Hủy. Đơn không tồn tại hoặc đã xử lý.")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi hủy booking: {e}")

@routerAdmin.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking_admin(booking_id: str, booking_update: BookingAdminUpdate):
    try:
        updated_booking = crud_booking.update_booking_by_admin(booking_id, booking_update)
        if not updated_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để cập nhật hoặc không có dữ liệu mới")
        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi cập nhật booking: {e}")

@routerAdmin.delete("/{booking_id}")
async def delete_booking_admin(booking_id: str):
    try:
        deleted_booking = crud_booking.delete_booking(booking_id)
        if not deleted_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để xóa")
        return {"message": "Xóa booking thành công", "booking_id": booking_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xóa booking: {e}")