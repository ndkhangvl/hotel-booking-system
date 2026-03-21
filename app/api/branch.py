from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from app.schema.branch import BranchCreate, BranchResponse, BranchUpdate, BranchPaginationResponse, BranchInitializeResponse, BranchDetailResponse
from app.crud import branch as crud_branch
from app.crud.audit import log_audit_event

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
        "branch_code": row[0], "name": row[1], "address": row[2], "phone": row[3],
        "created_date": row[4], "created_time": row[5], "created_user": row[6],
        "updated_date": row[7], "updated_time": row[8], "updated_user": row[9],
        "del_flg": row[10]
    }

@router.post("/", response_model=BranchResponse)
async def upsert_branch(branch_data: BranchUpdate):
    try:
        if branch_data.branch_code:
            row = crud_branch.update_branch(branch_data.branch_code, branch_data)
            action = "cập nhật"
        else:
            if not branch_data.name or not branch_data.address:
                raise HTTPException(status_code=400, detail="Thiếu thông tin bắt buộc")
            row = crud_branch.create_branch(branch_data)
            action = "tạo mới"

        if not row:
            raise HTTPException(status_code=404, detail=f"Không thể {action} chi nhánh")
        
        await log_audit_event(
            action="UPDATE" if branch_data.branch_code else "CREATE",
            entity_type="branch",
            source_table="branches",
            entity_pk={"branch_code": row["branch_code"]},
            branch_code=row["branch_code"],
            actor_role="Admin",
            endpoint="/admin/branches/",
            method="POST",
            message=f"{action.capitalize()} chi nhánh thành công"
        )

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


@routerForUser.get("/{branch_code}", response_model=BranchDetailResponse)
async def read_branch_for_user(branch_code: str):
    row = crud_branch.get_active_branch_detail(branch_code)
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh")
    return row
    
@router.get("/{branch_code}", response_model=BranchResponse)
async def get_any_branch(branch_code: str):
    row = crud_branch.get_branch_by_id(branch_code, active_only=False)
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh")
    return row