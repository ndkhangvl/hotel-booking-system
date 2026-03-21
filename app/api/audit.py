from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.schema.audit import AuditLogListResponse
from app.crud.audit import get_audit_logs

router = APIRouter(prefix="/admin/audits", tags=["Admin - Audit Logs"])

@router.get("/", response_model=AuditLogListResponse)
async def fetch_audit_logs(
    branch_code: Optional[str] = Query(None, description="Lọc theo branch_code"),
    action: Optional[str] = Query(None, description="Lọc theo action (CREATE, UPDATE, DELETE)"),
    entity_type: Optional[str] = Query(None, description="Lọc theo module/entity (booking, room, branch...)"),
    keyword: Optional[str] = Query(None, description="Từ khóa tìm kiếm"),
    start_date: Optional[str] = Query(None, description="Ngày bắt đầu sự kiện (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Ngày kết thúc sự kiện (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    try:
        results = await get_audit_logs(
            branch_code=branch_code,
            action=action,
            entity_type=entity_type,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy danh sách logs: {e}")
