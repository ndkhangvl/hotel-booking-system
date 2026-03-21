from datetime import date
from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.schema.room import RoomInitializeResponse, RoomListResponse, RoomTypeResponse, AmenityResponse, RoomUpsertRequest, RoomResponse, BranchRoomListResponse, BranchRoomUpsertRequest, BranchRoomDeleteRequest
from app.crud import room as crud_room

router = APIRouter(prefix="/admin/rooms", tags=["Admin - Rooms"])
routerAmenities = APIRouter(prefix="/user", tags=["User - Amenities"])
routerForUser = APIRouter(prefix="/user/rooms", tags=["User - Rooms"])


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
    start_date: date | None = Query(default=None, description="Ngày bắt đầu xem trạng thái phòng"),
    end_date: date | None = Query(default=None, description="Ngày kết thúc xem trạng thái phòng"),
):
    """
    Trả về thống kê tổng quan phòng của một chi nhánh:
    - Tổng số phòng
    - Số phòng đang hoạt động (del_flg = 0)
    - Số phòng không hoạt động (del_flg != 0)
    """
    try:
        return crud_room.get_initialize_stats(branch_id=branch_id, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thống kê phòng: {e}")


@routerAmenities.get("/amenities", response_model=List[AmenityResponse])
async def amenities():
    """
    Trả về danh sách tất cả tiện ích đang hoạt động.
    """
    try:
        return crud_room.get_amenities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách tiện ích: {e}")

@router.get("/amenities", response_model=List[AmenityResponse])
async def amenities_for_admin():
    """
    Trả về danh sách tiện ích cho trang người dùng.
    """
    try:
        return crud_room.get_amenities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách tiện ích: {e}")

@routerForUser.get("/amenities", response_model=List[AmenityResponse])
async def amenities_for_user():
    """
    Trả về danh sách tiện ích cho trang người dùng.
    """
    try:
        return crud_room.get_amenities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách tiện ích: {e}")


@routerForUser.get("/rooms", response_model=List[RoomResponse])
async def rooms_for_user(
    limit: int = Query(default=4, ge=1, le=20, description="Số phòng cần lấy"),
):
    """
    Trả về danh sách phòng nổi bật cho trang người dùng.
    """
    try:
        return crud_room.get_user_rooms(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách phòng: {e}")


@routerAmenities.get("/room-types", response_model=List[RoomTypeResponse])
async def room_types_for_user(
    limit: int = Query(default=4, ge=1, le=20, description="Số loại phòng cần lấy"),
):
    """
    Trả về danh sách loại phòng cho trang người dùng.
    Dữ liệu lấy từ bảng room_types.
    """
    try:
        return crud_room.get_room_types()[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách loại phòng: {e}")


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
    start_date: date | None = Query(default=None, description="Ngày bắt đầu xem trạng thái phòng"),
    end_date: date | None = Query(default=None, description="Ngày kết thúc xem trạng thái phòng"),
    page: int = Query(default=1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Số bản ghi mỗi trang"),
):
    """
    Trả về danh sách phòng có phân trang cho một chi nhánh.
    Kèm tên loại phòng (JOIN room_types).
    """
    try:
        return crud_room.get_rooms_by_branch(branch_id, page, page_size, active_only=False, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách phòng: {e}")


@router.get("/branch-rooms-list", response_model=BranchRoomListResponse)
async def branch_rooms_list(
    branch_id: str = Query(..., description="UUID của chi nhánh"),
    start_date: date | None = Query(default=None, description="Ngày bắt đầu xem trạng thái phòng"),
    end_date: date | None = Query(default=None, description="Ngày kết thúc xem trạng thái phòng"),
    page: int = Query(default=1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Số bản ghi mỗi trang"),
):
    try:
        return crud_room.get_branch_rooms_by_branch(branch_id, page, page_size, start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách branch rooms: {e}")


@router.post("/branch-rooms", status_code=200)
async def upsert_branch_room(body: BranchRoomUpsertRequest):
    try:
        branch_room_id = crud_room.upsert_branch_room(body.model_dump())
        return {"branch_room_id": branch_room_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu branch room: {e}")


@router.delete("/branch-rooms", status_code=200)
async def remove_branch_room(body: BranchRoomDeleteRequest, branch_id: str = Query(..., description="UUID của chi nhánh")):
    deleted = crud_room.delete_branch_room(str(body.branch_room_id), branch_id=branch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy branch room")
    return {"success": True}

@routerForUser.get("/rooms-list", response_model=RoomListResponse)
async def user_get_active_rooms_by_branch(
    branch_id: str, page: int = 1, page_size: int = 10
    ):
    return crud_room.get_rooms_by_branch(branch_id, page, page_size, active_only=True)

@router.get("/{room_id}")
async def admin_get_room_info(room_id: str):
    """[ADMIN] Lấy thông tin chi tiết phòng (kể cả phòng đã xóa)"""
    room = crud_room.get_room_detail(room_id, active_only=False)
    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng")
    return room

@routerForUser.get("/{room_id}")
async def user_get_room_info(room_id: str):
    """[USER] Lấy thông tin phòng (chỉ phòng đang hoạt động)"""
    room = crud_room.get_room_detail(room_id, active_only=True)
    if not room:
        raise HTTPException(status_code=404, detail="Phòng không tồn tại hoặc đã ngừng hoạt động")
    return room