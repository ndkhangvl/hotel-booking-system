from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.schema.room import RoomInitializeResponse, RoomListResponse, RoomTypeResponse, AmenityResponse, RoomUpsertRequest
from app.crud import room as crud_room

router = APIRouter(prefix="/admin/rooms", tags=["Admin - Rooms"])


@router.post("", status_code=200)
async def upsert_room(body: RoomUpsertRequest):
    """
    Insert hoặc Update phòng (kèm cập nhật tiện ích).
    - Không gửi room_id (hoặc null) => INSERT mới.
    - Gửi room_id hợp lệ => UPDATE bản ghi đó.
    del_flg: 0=Còn Trống, 1=Đã Đặt, 2=Đang Sử Dụng, 3=Không Sử Dụng
    """
    try:
        room_id = crud_room.upsert_room(body.model_dump())
        return {"room_id": room_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu phòng: {e}")


@router.get("/initialize", response_model=RoomInitializeResponse)
async def initialize(
    branch_id: str = Query(..., description="UUID của chi nhánh"),
):
    """
    Trả về thống kê tổng quan phòng của một chi nhánh:
    - Tổng số phòng
    - Số phòng đang hoạt động (del_flg = 0)
    - Số phòng không hoạt động (del_flg != 0)
    """
    try:
        return crud_room.get_initialize_stats(branch_id=branch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thống kê phòng: {e}")


@router.get("/amenities", response_model=List[AmenityResponse])
async def amenities():
    """
    Trả về danh sách tất cả tiện ích đang hoạt động.
    """
    try:
        return crud_room.get_amenities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách tiện ích: {e}")


@router.get("/room-types", response_model=List[RoomTypeResponse])
async def room_types():
    """
    Trả về danh sách tất cả loại phòng đang hoạt động.
    """
    try:
        return crud_room.get_room_types()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách loại phòng: {e}")


@router.get("/rooms-list", response_model=RoomListResponse)
async def rooms_list(
    branch_id: str = Query(..., description="UUID của chi nhánh"),
    page: int = Query(default=1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Số bản ghi mỗi trang"),
):
    """
    Trả về danh sách phòng có phân trang cho một chi nhánh.
    Kèm tên loại phòng (JOIN room_types).
    """
    try:
        return crud_room.get_rooms_list(branch_id=branch_id, page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách phòng: {e}")
