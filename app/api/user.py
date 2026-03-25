from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List
from fastapi.security import OAuth2PasswordBearer
from app.schema.user import UserCreate, UserUpdate, UserResponse, UserLogin, Token, UserPaginationResponse
from app.crud import user as crud_user
from app.core import security 
from app.crud.audit import log_audit_event, log_audit_events_bulk

router = APIRouter(prefix="/users", tags=["Users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate):
    user = crud_user.get_user_by_email(user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="Email đã tồn tại")
    
    new_user = crud_user.create_user(user_in)
    
    await log_audit_event(
        action="CREATE",
        entity_type="user",
        source_table="users",
        entity_pk={"user_id": str(new_user.get("user_id"))},
        actor_role="User",
        endpoint="/users/register",
        method="POST",
        message="Đăng ký người dùng mới thành công"
    )
    
    return new_user

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

@router.get("/", response_model=UserPaginationResponse)
async def read_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(128, ge=1, le=200),
    token: str = Depends(oauth2_scheme)
):
    return crud_user.get_all_users(page=page, page_size=page_size)

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
        
    await log_audit_event(
        action="UPDATE",
        entity_type="user",
        source_table="users",
        entity_pk={"user_id": str(user_id)},
        actor_role="Admin/Manager",
        endpoint=f"/users/{user_id}",
        method="PUT",
        message="Cập nhật thông tin người dùng"
    )
        
    return updated

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, token: str = Depends(oauth2_scheme)):
    user = crud_user.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    crud_user.delete_user(user_id)
    
    await log_audit_event(
        action="DELETE",
        entity_type="user",
        source_table="users",
        entity_pk={"user_id": str(user_id)},
        actor_role="Admin",
        endpoint=f"/users/{user_id}",
        method="DELETE",
        message="Xóa người dùng"
    )

@router.post("/register/bulk", response_model=List[UserResponse])
async def register_bulk(users_in: List[UserCreate]):
    try:
        new_users = crud_user.create_users_bulk(users_in)
        
        # Audit logging
        audit_events = []
        for u in new_users:
            audit_events.append({
                "action": "CREATE",
                "entity_type": "user",
                "source_table": "users",
                "entity_pk": {"user_id": str(u.get("user_id"))},
                "actor_role": "Admin",
                "endpoint": "/users/register/bulk",
                "method": "POST",
                "message": "Đăng ký bulk người dùng mới"
            })
            
        if audit_events:
            await log_audit_events_bulk(audit_events)
            
        return new_users
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đăng ký bulk users: {str(e)}")