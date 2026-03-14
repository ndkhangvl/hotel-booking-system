from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import date


class BranchResponse(BaseModel):
    branch_id: UUID
    name: str
    address: str
    phone: Optional[str] = None
    total_rooms: int
    created_date: Optional[date] = None
    del_flg: int

    class Config:
        from_attributes = True


class BranchListResponse(BaseModel):
    items: List[BranchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BranchInitializeResponse(BaseModel):
    total_branches: int
    active_branches: int
    total_rooms: int
