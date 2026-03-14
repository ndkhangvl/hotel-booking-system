from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from uuid import UUID
from app.schema.branch import BranchCreate, BranchResponse, BranchUpdate, BranchResponse, BranchPaginationResponse
from app.crud import branch as crud_branch

router = APIRouter(prefix="/admin/branches", tags=["Admin - Branches"])
routerForUser = APIRouter(prefix="/user/branches", tags=["User - Branches"])

@router.get("/initialize", response_model=BranchResponse)
async def initialize():
    """
    Trả về thống kê tổng quan cho trang quản lý chi nhánh:
    - Tổng số chi nhánh
    - Số chi nhánh đang hoạt động (del_flg = 0)
    - Tổng số phòng (JOIN branches + rooms)
    """
    try:
        return crud_branch.get_initialize_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy thống kê chi nhánh: {e}")


@router.get("/branches-list", response_model=BranchPaginationResponse)
async def branches_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100)
):
    try:
        # Nhờ dict_row, hàm này trả về cấu trúc dict lồng nhau 
        # mà Pydantic có thể đọc được ngay lập tức.
        return crud_branch.get_branches_list(page=page, page_size=page_size)
    except Exception as e:
        print(f"Error logic: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")
    
@router.post("/", response_model=BranchResponse)
async def create_new_branch(branch: BranchCreate):
    try:
        row = crud_branch.create_branch(branch)
        if not row:
            raise HTTPException(status_code=400, detail="Không thể tạo chi nhánh")
        
        # Map thủ công từ tuple sang dict
        return {
            "branch_id": row[0],
            "name": row[1],
            "address": row[2],
            "phone": row[3],
            "created_date": row[4],
            "created_time": row[5],
            "created_user": row[6],
            "updated_date": row[7],
            "updated_time": row[8],
            "updated_user": row[9],
            "del_flg": row[10]
        }
    except Exception as e:
        # log lỗi ra console để debug nếu cần
        print(f"Error detail: {e}")
        raise HTTPException(status_code=400, detail=f"Lỗi tạo chi nhánh: {str(e)}")

@routerForUser.get("/branches-list", response_model=BranchPaginationResponse)
async def branches_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100)
):
    try:
        # Nhờ dict_row, hàm này trả về cấu trúc dict lồng nhau 
        # mà Pydantic có thể đọc được ngay lập tức.
        return crud_branch.get_all_active_branches(page=page, page_size=page_size)
    except Exception as e:
        print(f"Error logic: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")

@routerForUser.get("/search", response_model=BranchPaginationResponse)
async def search_branches_api(
    keyword: str = Query(..., min_length=1, description="Từ khóa tìm kiếm (tên, địa chỉ)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """
    Tìm kiếm chi nhánh theo tên hoặc địa chỉ (không phân biệt hoa thường).
    """
    try:
        # Gọi hàm từ crud_branch
        return crud_branch.search_branches(keyword=keyword, page=page, page_size=page_size)
    except Exception as e:
        # Log lỗi thực tế ra console để debug
        print(f"Search Error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi tìm kiếm chi nhánh")
    
@router.get("/{branch_id}", response_model=BranchResponse)
async def read_branch(branch_id: UUID):
    row = crud_branch.get_branch_by_id(branch_id)
    
    # Kiểm tra nếu không tìm thấy dữ liệu
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh")
    
    # 'row' hiện tại là một tuple: (UUID(...), 'Aurora Trà Vinh', ...)
    # Chúng ta cần chuyển nó thành dict để Pydantic validate được
    return {
        "branch_id": row[0],
        "name": row[1],
        "address": row[2],
        "phone": row[3],
        "created_date": row[4],
        "created_time": row[5],
        "created_user": row[6],
        "updated_date": row[7],
        "updated_time": row[8],
        "updated_user": row[9],
        "del_flg": row[10]
    }

@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_existing_branch(branch_id: UUID, branch_data: BranchUpdate):
    row = crud_branch.update_branch(branch_id, branch_data)
    
    if not row:
        raise HTTPException(
            status_code=404, 
            detail="Không tìm thấy chi nhánh hoặc không có dữ liệu thay đổi"
        )
    
    # Map từ tuple sang dict
    return {
        "branch_id": row[0],
        "name": row[1],
        "address": row[2],
        "phone": row[3],
        "created_date": row[4],
        "created_time": row[5],
        "created_user": row[6],
        "updated_date": row[7],
        "updated_time": row[8],
        "updated_user": row[9],
        "del_flg": row[10]
    }

@router.delete("/{branch_id}", response_model=BranchResponse)
async def soft_delete_branch(branch_id: UUID, current_user_id: UUID):
    # current_user_id hiện tại đang truyền qua query parameter, 
    # sau này bạn nên lấy từ JWT token để bảo mật hơn.
    row = crud_branch.delete_branch(branch_id, current_user_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh để xóa")
    
    # Map từ tuple sang dict
    return {
        "branch_id": row[0],
        "name": row[1],
        "address": row[2],
        "phone": row[3],
        "created_date": row[4],
        "created_time": row[5],
        "created_user": row[6],
        "updated_date": row[7],
        "updated_time": row[8],
        "updated_user": row[9],
        "del_flg": row[10]
    }