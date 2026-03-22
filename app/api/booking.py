from fastapi import APIRouter, HTTPException
from typing import List
from app.schema.booking import BookingAdminCreate, BookingCreate, BookingResponse, BookingAdminResponse, BookingAdminUpdate
from app.crud import booking as crud_booking
from app.utils.email_queue import enqueue_booking_confirmation_email
from app.crud.audit import log_audit_event
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.security import SECRET_KEY, ALGORITHM
from app.crud.user import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

router = APIRouter(prefix="/bookings", tags=["Bookings"])
routerReceptionist = APIRouter(prefix="/Receptionist/bookings", tags=["receptionist - Bookings"])
routerAdmin = APIRouter(prefix="/Admin/bookings", tags=["Admin - Bookings"])

@router.post("/user/", response_model=BookingResponse)
async def create_new_booking(booking: BookingCreate):
    try:
        created_booking = crud_booking.create_booking(booking)
        await enqueue_booking_confirmation_email(created_booking)
        
        await log_audit_event(
            action="CREATE",
            branch_code=created_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(created_booking.get("booking_id", "")),
            booking_code=created_booking.get("booking_code", ""),
            actor_id=str(booking.user_id) if booking.user_id else None,
            endpoint="/bookings/user/",
            method="POST",
            message="Tạo booking mới từ User"
        )
        
        return created_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo booking: {e}")

from fastapi import Depends

@router.get("/user/me", response_model=List[BookingAdminResponse])
async def read_my_bookings(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token không hợp lệ")
        
        user_db = get_user_by_id(user_id)
        if not user_db:
            raise HTTPException(status_code=401, detail="Không tìm thấy người dùng")

        bookings = crud_booking.get_bookings_by_user_id(user_id)
        return bookings
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy lịch sử đặt phòng: {str(e)}")


@routerReceptionist.get("/", response_model=List[BookingResponse])
async def read_bookings_for_receptionist():
    try:
        return crud_booking.get_all_bookings()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi lấy danh sách booking: {e}")


@routerAdmin.get("/", response_model=List[BookingAdminResponse])
async def read_bookings_for_admin():
    try:
        return crud_booking.get_all_bookings_with_details()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi lấy danh sách booking admin: {e}")


@routerAdmin.post("/", response_model=BookingResponse)
async def create_booking_admin(booking: BookingAdminCreate):
    try:
        created_booking = crud_booking.create_booking(booking)
        await enqueue_booking_confirmation_email(created_booking)

        await log_audit_event(
            action="CREATE",
            branch_code=created_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(created_booking.get("booking_id", "")),
            booking_code=created_booking.get("booking_code", ""),
            actor_role="Admin",
            endpoint="/Admin/bookings/",
            method="POST",
            message="Tạo booking mới từ Admin"
        )

        return created_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo booking admin: {e}")

@routerReceptionist.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking_api(booking_id: str):
    try:
        updated_booking = crud_booking.confirm_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Xác nhận. Đơn không ở trạng thái Pending.")

        await log_audit_event(
            action="UPDATE",
            branch_code=updated_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(updated_booking.get("booking_id", "")),
            booking_code=updated_booking.get("booking_code", ""),
            actor_role="Receptionist",
            endpoint=f"/Receptionist/bookings/{booking_id}/confirm",
            method="PATCH",
            reason="Xác nhận booking",
            message="Cập nhật trạng thái thành Confirmed"
        )

        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xác nhận booking: {e}")

@routerReceptionist.patch("/{booking_id}/check-in", response_model=BookingResponse)
async def check_in_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_in(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-in. Đơn chưa được Confirmed.")
        
        await log_audit_event(
            action="UPDATE",
            branch_code=updated_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(updated_booking.get("booking_id", "")),
            booking_code=updated_booking.get("booking_code", ""),
            actor_role="Receptionist",
            endpoint=f"/Receptionist/bookings/{booking_id}/check-in",
            method="PATCH",
            reason="Check-in",
            message="Cập nhật trạng thái thành Checked-in"
        )

        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-in: {e}")

@routerReceptionist.patch("/{booking_id}/check-out", response_model=BookingResponse)
async def check_out_booking(booking_id: str):
    try:
        updated_booking = crud_booking.process_check_out(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Check-out. Khách chưa Check-in.")

        await log_audit_event(
            action="UPDATE",
            branch_code=updated_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(updated_booking.get("booking_id", "")),
            booking_code=updated_booking.get("booking_code", ""),
            actor_role="Receptionist",
            endpoint=f"/Receptionist/bookings/{booking_id}/check-out",
            method="PATCH",
            reason="Check-out",
            message="Cập nhật trạng thái thành Completed"
        )

        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Check-out: {e}")

@routerReceptionist.patch("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking_api(booking_id: str):
    try:
        updated_booking = crud_booking.cancel_booking(booking_id)
        if not updated_booking:
            raise HTTPException(status_code=400, detail="Không thể Hủy. Đơn không tồn tại hoặc đã xử lý.")

        await log_audit_event(
            action="UPDATE",
            branch_code=updated_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(updated_booking.get("booking_id", "")),
            booking_code=updated_booking.get("booking_code", ""),
            actor_role="Receptionist",
            endpoint=f"/Receptionist/bookings/{booking_id}/cancel",
            method="PATCH",
            reason="Hủy booking",
            message="Cập nhật trạng thái thành Cancelled"
        )

        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi hủy booking: {e}")

@routerAdmin.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking_admin(booking_id: str, booking_update: BookingAdminUpdate):
    try:
        updated_booking = crud_booking.update_booking_by_admin(booking_id, booking_update)
        if not updated_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để cập nhật hoặc không có dữ liệu mới")

        await log_audit_event(
            action="UPDATE",
            branch_code=updated_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(updated_booking.get("booking_id", "")),
            booking_code=updated_booking.get("booking_code", ""),
            actor_role="Admin",
            endpoint=f"/Admin/bookings/{booking_id}",
            method="PATCH",
            reason="Admin cập nhật đơn",
            message="Cập nhật thông tin booking thành công"
        )

        return updated_booking
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi cập nhật booking: {e}")

@routerAdmin.delete("/{booking_id}")
async def delete_booking_admin(booking_id: str):
    try:
        deleted_booking = crud_booking.delete_booking(booking_id)
        if not deleted_booking:
            raise HTTPException(status_code=404, detail="Không tìm thấy booking để xóa")

        await log_audit_event(
            action="DELETE",
            branch_code=deleted_booking.get("branch_code", "UNKNOWN"),
            booking_id=str(deleted_booking.get("booking_id", "")),
            booking_code=deleted_booking.get("booking_code", ""),
            actor_role="Admin",
            endpoint=f"/Admin/bookings/{booking_id}",
            method="DELETE",
            reason="Admin xóa đơn",
            message="Xóa (soft delete) booking thành công"
        )

        return {"message": "Xóa booking thành công", "booking_id": booking_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi xóa booking: {e}")