from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from uuid import UUID
from app.schema.branch import BranchCreate, BranchResponse, BranchUpdate, BranchResponse, BranchPaginationResponse, BranchInitializeResponse
from app.crud import branch as crud_branch

router = APIRouter(prefix="/admin/branches", tags=["Admin - Branches"])
routerForUser = APIRouter(prefix="/user/branches", tags=["User - Branches"])

@router.get("/initialize", response_model=BranchInitializeResponse)
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

def map_branch_row(row):
    if not row: return None
    return {
        "branch_id": row[0], "name": row[1], "address": row[2], "phone": row[3],
        "created_date": row[4], "created_time": row[5], "created_user": row[6],
        "updated_date": row[7], "updated_time": row[8], "updated_user": row[9],
        "del_flg": row[10]
    }

@router.post("/", response_model=BranchResponse)
async def upsert_branch(branch_data: BranchUpdate):
    try:
        if branch_data.branch_id:
            row = crud_branch.update_branch(branch_data.branch_id, branch_data)
            action = "cập nhật"
        else:
            if not branch_data.name or not branch_data.address:
                raise HTTPException(status_code=400, detail="Thiếu thông tin bắt buộc")
            row = crud_branch.create_branch(branch_data)
            action = "tạo mới"

        if not row:
            raise HTTPException(status_code=404, detail=f"Không thể {action} chi nhánh")
        
        # Vì row đã là Dict (do dict_row), trả về luôn!
        return row 

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
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
async def get_any_branch(branch_id: UUID):
    row = crud_branch.get_branch_by_id(branch_id, active_only=False)
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh")
    return row

@routerForUser.get("/{branch_id}", response_model=BranchResponse)
async def get_active_branch(branch_id: UUID):
    row = crud_branch.get_branch_by_id(branch_id, active_only=True)
    if not row:
        raise HTTPException(status_code=404, detail="Chi nhánh không tồn tại hoặc đã đóng cửa")
    return row

@router.delete("/{branch_id}", response_model=BranchResponse)
async def soft_delete_branch(branch_id: UUID):
    """
    Xóa mềm chi nhánh (chuyển del_flg = 1)
    """
    try:
        row = crud_branch.delete_branch(branch_id)
        
        if not row:
            raise HTTPException(
                status_code=404, 
                detail="Không tìm thấy chi nhánh để xóa"
            )
            
        return row # Trả về trực tiếp vì crud đã dùng dict_row
        
    except Exception as e:
        print(f"Delete Error: {e}")
        raise HTTPException(status_code=400, detail=f"Lỗi khi xóa chi nhánh: {str(e)}")
    

@router.post("/{branch_id}", response_model=BranchResponse)
async def restore_existing_branch(branch_id: UUID):
    """
    [ADMIN] Khôi phục chi nhánh đã bị xóa mềm.
    Các phòng thuộc chi nhánh vẫn sẽ ở trạng thái ẩn (del_flg=1).
    """
    try:
        row = crud_branch.restore_branch(branch_id)
        
        if not row:
            raise HTTPException(
                status_code=404, 
                detail="Không tìm thấy chi nhánh hoặc chi nhánh không tồn tại."
            )
            
        return row # Trả về trực tiếp vì crud đã dùng dict_row
        
    except Exception as e:
        print(f"Restore Branch Error: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi khôi phục chi nhánh: {str(e)}")