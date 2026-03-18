from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from fastapi.security import OAuth2PasswordBearer
from app.schema.user import UserCreate, UserUpdate, UserResponse, UserLogin, Token
from app.crud import user as crud_user
from app.core import security 

router = APIRouter(prefix="/users", tags=["Users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate):
    user = crud_user.get_user_by_email(user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="Email đã tồn tại")
    
    return crud_user.create_user(user_in)

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin):
    user = crud_user.get_user_by_email(login_data.email)
    
    if not user or not security.verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Không đúng email hoặc password"
        )
    
    # Tạo JWT token, truyền thêm role vào
    access_token = security.create_access_token(user["user_id"], user.get("role"))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/", response_model=List[UserResponse])
async def read_users(token: str = Depends(oauth2_scheme)):
    return crud_user.get_all_users()

@router.get("/{user_id}", response_model=UserResponse)
async def read_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user = crud_user.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_in: UserUpdate, token: str = Depends(oauth2_scheme)):
    user = crud_user.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    if user_in.email is not None:
        existing = crud_user.get_user_by_email(user_in.email)
        if existing and str(existing["user_id"]) != user_id:
            raise HTTPException(status_code=400, detail="Email đã được sử dụng bởi tài khoản khác")
    updated = crud_user.update_user(user_id, user_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return updated

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user = crud_user.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    crud_user.delete_user(user_id)