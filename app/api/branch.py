from fastapi import APIRouter, HTTPException, Query
from app.schema.branch import BranchInitializeResponse, BranchListResponse
from app.crud import branch as crud_branch

router = APIRouter(prefix="/admin/branches", tags=["Admin - Branches"])


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


@router.get("/branches-list", response_model=BranchListResponse)
async def branches_list(
    page: int = Query(default=1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Số bản ghi mỗi trang"),
):
    """
    Trả về danh sách chi nhánh có phân trang.
    Mỗi chi nhánh bao gồm tổng số phòng (JOIN với bảng rooms).
    """
    try:
        return crud_branch.get_branches_list(page=page, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách chi nhánh: {e}")
