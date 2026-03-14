from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID
from app.schema.branch import BranchCreate, BranchResponse, BranchUpdate
from app.crud import branch as crud_branch

router = APIRouter(prefix="/branches", tags=["Branches"])

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

@router.get("/", response_model=List[BranchResponse])
async def read_branches():
    return crud_branch.get_all_branches()

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