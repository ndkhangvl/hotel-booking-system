from fastapi import APIRouter, HTTPException
from typing import List
from uuid import UUID
from app.schema.room import RoomResponseWithTypeName
from app.crud import room as crud_room

routerForUser = APIRouter(prefix="/user/rooms", tags=["User - Rooms"])

@routerForUser.get("/branch/{branch_id}", response_model=List[RoomResponseWithTypeName])
async def get_branch_rooms(branch_id: UUID):
    """
    Lấy danh sách tất cả các phòng thuộc về một chi nhánh cụ thể.
    """
    try:
        rooms = crud_room.get_rooms_by_branch(branch_id)
        # FastAPI + Pydantic sẽ tự động validate list các dict này
        return rooms
    except Exception as e:
        print(f"Error fetching rooms for branch {branch_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Lỗi khi lấy danh sách phòng của chi nhánh: {str(e)}"
        )