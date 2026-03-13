from fastapi import APIRouter, HTTPException
from typing import List
from app.schema.user import UserCreate, UserResponse
from app.crud import user as crud_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse)
async def create_new_user(user: UserCreate):
    try:
        return crud_user.create_user(user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi tạo user: {e}")

@router.get("/", response_model=List[UserResponse])
async def read_users():
    return crud_user.get_all_users()

@router.get("/{user_id}", response_model=UserResponse)
async def read_user(user_id: str):
    user = crud_user.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return user